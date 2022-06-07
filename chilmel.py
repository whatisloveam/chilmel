# chilmel.py
# Part of the chilmel driver for Inkscape
#
# Requires Pyserial 3.0 recommended.

import sys
sys.path.append('lib')

import inkex
from simpletransform import *
import simplepath

from math import sqrt
from array import *
import gettext
import serial
import string
import time

import grbl_serial
from grbl_serial import GrblSerial
from grbl_motion import GrblMotion
import plot_utils   # https://github.com/evil-mad/plotink

import chilmel_conf  # Настройки можно менять здесь

import builtins

from inkex.paths import *
from inkex.transforms import *
from inkex import bezier
from lxml import etree

# Преобразование имен типов в типы (связано с миграцией в связи с разными версиями)
def GetArgumentTypeFromName(type_name):
    try:
        # Cater for non-built-in type as per
        # https://wiki.inkscape.org/wiki/index.php/Updating_your_Extension_for_1.0#Collecting_the_options_of_the_extension
        if type_name == 'inkbool':
            return inkex.Boolean
            
        return getattr(builtins, type_name)
    except AttributeError:
        return None

def AppendCommand(a, command, data):
    a.append([command.strip(), data])


xrange = range

class ChilMelClass(inkex.Effect):

  def add_option(self, name, action, type, dest, default, help):
    self.arg_parser.add_argument(name,
      action=action, type=GetArgumentTypeFromName(type),
      dest=dest, default=default,
      help=help)


  def add_option_store_true(self, name, dest, help):
    self.arg_parser.add_argument(name,
      action="store_true",
      dest=dest,
      help=help)

  def __init__(self):
    inkex.Effect.__init__(self)
    self.start_time = time.time()
    self.doLogDebug = False
    
    self.add_option("--mode",
      action="store", type="string",
      dest="mode", default="plot",
      help="Выбран режим (или вкладка GUI)")

    self.add_option("--penUpPosition",
      action="store", type="int",
      dest="penUpPosition", default=chilmel_conf.PenUpPos,
      help="Положение пера в поднятом состоянии")
      
    self.add_option("--penDownPosition",
      action="store", type="int",
      dest="penDownPosition", default=chilmel_conf.PenDownPos,
      help="Положение пера для рисования")  
      
    self.add_option("--setupType",
      action="store", type="string",
      dest="setupType", default="align-mode",
      help="Выбранный вариант установки")

    self.add_option("--applySpeed",
      action="store", type="inkbool",
      dest="applySpeed", default=chilmel_conf.applySpeed,
      help="Применять ли скорость к перу")

    self.add_option("--penDownSpeed",
      action="store", type="int",
      dest="penDownSpeed", default=chilmel_conf.PenDownSpeed,
      help="Скорость (мм/мин), когда перо опущено")

    self.add_option("--penUpSpeed",
      action="store", type="int",
      dest="penUpSpeed", default=chilmel_conf.PenUpSpeed,
      help="Скорость перемещения (мм/мин), когда перо поднято")

    self.add_option("--penLiftRate",
      action="store", type="int",
      dest="penLiftRate", default=chilmel_conf.penLiftRate,
      help="Скорость подъема пера ")
    self.add_option("--penLiftDelay",
      action="store", type="int",
      dest="penLiftDelay", default=chilmel_conf.penLiftDelay,
      help="задержка после поднятия пера (мс)")
      
    self.add_option("--penLowerRate",
      action="store", type="int",
      dest="penLowerRate", default=chilmel_conf.penLowerRate,
      help="Скорость опускания пера") 
    self.add_option("--penLowerDelay",
      action="store", type="int",
      dest="penLowerDelay", default=chilmel_conf.penLowerDelay,
      help="задержка после опускания пера (мс)")

    self.add_option("--autoRotate",
      action="store", type="inkbool",
      dest="autoRotate", default=chilmel_conf.autoRotate,
      help="Автоматическая печать в вертикально или горизонтально режиме")

    self.add_option("--constSpeed",
      action="store", type="inkbool",
      dest="constSpeed", default=chilmel_conf.constSpeed,
      help="Использовать режим постоянной скорости, когда перо опущено")
      
    self.add_option("--reportTime",
      action="store", type="inkbool",
      dest="reportTime", default=chilmel_conf.reportTime,
      help="Выводить время исполнения")

    self.add_option("--logSerial",
      action="store", type="inkbool",
      dest="logSerial", default=chilmel_conf.logSerial,
      help="вести журнал последовательной связи")

    self.add_option("--smoothness",
      action="store", type="float",
      dest="smoothness", default=chilmel_conf.smoothness,
      help="Плавность кривых")

    self.add_option("--cornering",
      action="store", type="float",
      dest="cornering", default=chilmel_conf.smoothness,
      help="Коэффициент скорости прохождения поворотов")

    self.add_option("--manualType",
      action="store", type="string",
      dest="manualType", default="version-check",
      help="Активная опция при нажатии кнопки «Применить»")

    self.add_option("--WalkDistance",
      action="store", type="float",
      dest="WalkDistance", default=1,
      help="Расстояние для перемешения каретки")

    self.add_option("--grblCommand",
      action="store", type="string",
      dest="grblCommand", default="$$",
      help="Команда GRBL для выполнения")

    self.add_option("--resumeType",
      action="store", type="string",
      dest="resumeType", default="ResumeNow",
      help="Активная опция при нажатии кнопки «Применить»")
      
    self.add_option("--layerNumber",
      action="store", type="int",
      dest="layerNumber", default=chilmel_conf.DefaultLayer,
      help="Выбранный слой для многослойной печати")

    self.add_option("--fileOutput",
      action="store", type="inkbool",
      dest="fileOutput", default=chilmel_conf.fileOutput,
      help="Вывод обновленного содержимого SVG на стандартный вывод")

    self.boundingBox = False
    self.add_option_store_true("--boundingBox",
      dest="boundingBox",
      help="Рисовать рамку")
      
    self.bb = { 'minX': 1e6, 'minY': 1e6, 'maxX': -1e6, 'maxY': -1e6 }
    
    self.serialPort = None
    self.bPenIsUp = None  # Исходное состояние пера ни вверх, ни вниз, а _unknown_.
    self.virtualPenIsUp = False  # Отслеживает открытую позицию при переходе по графику перед возобновлением
    self.ignoreLimits = False


    fX = None
    fY = None 
    self.fCurrX = chilmel_conf.StartPosX
    self.fCurrY = chilmel_conf.StartPosY 
    self.ptFirst = (chilmel_conf.StartPosX, chilmel_conf.StartPosY)
    self.bStopped = False
    self.fSpeed = 1
    self.resumeMode = False
    self.nodeCount = int(0)   # NOTE: python uses 32-bit ints.
    self.nodeTarget = int(0)
    self.pathcount = int(0)
    self.LayersFoundToPlot = False
    self.LayerOverrideSpeed = False
    self.LayerOverridePenDownHeight = False
    self.LayerPenDownPosition = -1
    self.LayerPenDownSpeed = -1

    self.penUpDistance = 0.0
    self.penDownDistance = 0.0
    
    # Значения, прочитанные из файла:
    self.svgLayer_Old = int(0)
    self.svgNodeCount_Old = int(0)
    self.svgDataRead_Old = False
    self.svgLastPath_Old = int(0)
    self.svgLastPathNC_Old = int(0)
    self.svgLastKnownPosX_Old = float(0.0)
    self.svgLastKnownPosY_Old = float(0.0)
    self.svgPausedPosX_Old = float(0.0)
    self.svgPausedPosY_Old = float(0.0) 
    
    # Новые значения для записи в файл:
    self.svgLayer = int(0)
    self.svgNodeCount = int(0)
    self.svgDataRead = False
    self.svgLastPath = int(0)
    self.svgLastPathNC = int(0)
    self.svgLastKnownPosX = float(0.0)
    self.svgLastKnownPosY = float(0.0)
    self.svgPausedPosX = float(0.0)
    self.svgPausedPosY = float(0.0) 
    
    self.PrintInLayersMode = False

    self.svgWidth = 0 
    self.svgHeight = 0
    self.printPortrait = False
    
    self.xBoundsMax = chilmel_conf.PageWidthIn
    self.xBoundsMin = chilmel_conf.StartPosX
    self.yBoundsMax = chilmel_conf.PageHeightIn
    self.yBoundsMin = chilmel_conf.StartPosY
    
    self.svgTransform = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    
    self.stepsPerInch = 0 # должна быть установлена в ненулевое значение перед рисованием.
    self.PenDownSpeed = chilmel_conf.PenDownSpeed * chilmel_conf.SpeedScale # Скорость по умолчанию, когда перо опущено  
    self.PenUpSpeed = 0.75 * chilmel_conf.SpeedScale # Скорость по умолчанию, когда перо поднято

    # Неподдерживаемые элементы SVG будут добавлены в словарь для отслеживания
    self.warnings = {}
    self.warnOutOfBounds = False

  def logDebug(self, msg):
    if not self.doLogDebug:
      return
    try:
      with open("4xidraw-debug.log", "a") as myfile:
        myfile.write('%s\n' % msg)
    except:
      inkex.errormsg(gettext.gettext("Ошибка записи данных."))
    

  def createMotion(self):
    self.motion = GrblMotion(self.serialPort, chilmel_conf.DPI_16X, self.options.penUpPosition, self.options.penDownPosition)

  def effect(self):
    '''Основная точка входа: проверяет, какой режим/вкладка выбрана, и действуйте соответствующим образом.'''

    self.svg = self.document.getroot()
    useOldResumeData = True
    skipSerial = False
    
    self.options.mode = self.options.mode.strip("\"")
    self.options.setupType = self.options.setupType.strip("\"")
    self.options.manualType = self.options.manualType.strip("\"")
    self.options.resumeType = self.options.resumeType.strip("\"")

    if (self.options.mode == "Help"):
      skipSerial = True
    if (self.options.mode == "options"):
      skipSerial = True   
    if (self.options.mode == "timing"):
      skipSerial = True
    if (self.options.mode == "manual"):
      if (self.options.manualType == "none"):
        skipSerial = True
      
    if skipSerial == False:
      self.serialPort = grbl_serial.openPort(self.options.logSerial)
      if self.serialPort is None:
        inkex.errormsg(gettext.gettext("Не могу подключиться. :("))
        sys.exit
      else:
        self.createMotion()

      if self.options.mode == "plot": 
        self.LayersFoundToPlot = False
        useOldResumeData = False
        self.PrintInLayersMode = False
        self.plotCurrentLayer = True
        self.svgNodeCount = 0
        self.svgLastPath = 0
        self.svgLayer = 12345;  # номер слоя для рисования всех слоев
        if self.serialPort is not None:
          self.plotDocument()
        if self.options.boundingBox:
          print("Bounding box: %d %d %d %d" % (self.bb['minX'], self.bb['minY'], self.bb['maxX'], self.bb['maxY']))
          self.options.boundingBox = False
          self.plotSegment(self.bb['minX'], self.bb['minY'])
          self.plotSegment(self.bb['minX'], self.bb['maxY'])
          self.plotSegment(self.bb['maxX'], self.bb['maxY'])
          self.plotSegment(self.bb['maxX'], self.bb['minY'])
          self.plotSegment(self.bb['minX'], self.bb['minY'])
          
      elif self.options.mode == "resume":
        useOldResumeData = False
        self.resumePlotSetup()
        if self.resumeMode:
          fX = self.svgPausedPosX_Old + chilmel_conf.StartPosX
          fY = self.svgPausedPosY_Old + chilmel_conf.StartPosY
          self.resumeMode = False
          self.plotSegment(fX, fY)
            
          self.resumeMode = True
          self.nodeCount = 0
          self.plotDocument() 
            
        elif (self.options.resumeType == "justGoHome"):
          fX = chilmel_conf.StartPosX
          fY = chilmel_conf.StartPosY 

          self.plotSegment(fX, fY)
              
          # Новые значения для записи в файл:
          self.svgNodeCount = self.svgNodeCount_Old
          self.svgLastPath = self.svgLastPath_Old 
          self.svgLastPathNC = self.svgLastPathNC_Old 
          self.svgPausedPosX = self.svgPausedPosX_Old 
          self.svgPausedPosY = self.svgPausedPosY_Old
          self.svgLayer = self.svgLayer_Old 
        else:
          inkex.errormsg(gettext.gettext("Кажется, нет никакого незавершенного пути, который можно было бы возобновить."))
  
      elif self.options.mode == "layers":
        useOldResumeData = False 
        self.PrintInLayersMode = True
        self.plotCurrentLayer = False
        self.LayersFoundToPlot = False
        self.svgLastPath = 0
        self.svgNodeCount = 0;
        self.svgLayer = self.options.layerNumber
        self.plotDocument()

      elif self.options.mode == "setup":
        self.setupCommand()
        
      elif self.options.mode == "manual":
        useOldResumeData = False 
        self.svgNodeCount = self.svgNodeCount_Old
        self.svgLastPath = self.svgLastPath_Old 
        self.svgLastPathNC = self.svgLastPathNC_Old 
        self.svgPausedPosX = self.svgPausedPosX_Old 
        self.svgPausedPosY = self.svgPausedPosY_Old
        self.svgLayer = self.svgLayer_Old 
        self.manualCommand()

    if (useOldResumeData):  # Не вносите никаких изменений в данные, сохраненные из файла SVG.
      self.svgNodeCount = self.svgNodeCount_Old
      self.svgLastPath = self.svgLastPath_Old 
      self.svgLastPathNC = self.svgLastPathNC_Old 
      self.svgPausedPosX = self.svgPausedPosX_Old 
      self.svgPausedPosY = self.svgPausedPosY_Old
      self.svgLayer = self.svgLayer_Old       
      self.svgLastKnownPosX = self.svgLastKnownPosX_Old
      self.svgLastKnownPosY = self.svgLastKnownPosY_Old 

    self.svgDataRead = False
    if self.serialPort is not None:
      self.serialPort.close()
    
  def resumePlotSetup(self):
    self.LayerFound = False
    if (self.svgLayer_Old < 101) and (self.svgLayer_Old >= 0):
      self.options.layerNumber = self.svgLayer_Old 
      self.PrintInLayersMode = True
      self.plotCurrentLayer = False
      self.LayerFound = True
    elif (self.svgLayer_Old == 12345):  # рисовать все слои
      self.PrintInLayersMode = False
      self.plotCurrentLayer = True
      self.LayerFound = True  
    if (self.LayerFound):
      if (self.svgNodeCount_Old > 0):
        self.nodeTarget = self.svgNodeCount_Old
        self.svgLayer = self.svgLayer_Old
        if self.options.resumeType == "ResumeNow":
          self.resumeMode = True
        self.penUp() 
        self.EnableMotors()
        self.fSpeed = self.PenDownSpeed 
        
        self.fCurrX = self.svgLastKnownPosX_Old + chilmel_conf.StartPosX
        self.fCurrY = self.svgLastKnownPosY_Old + chilmel_conf.StartPosY
         
  def setupCommand(self):
    self.createMotion()
    
    if self.options.setupType == "align-mode":
      self.penUp()

    elif self.options.setupType == "toggle-pen":
      self.penUp()
      time.sleep(1)
      self.penDown()

  def manualCommand(self):
    if self.options.manualType == "none":
      return
      
    self.createMotion()
    
    if self.serialPort is None:
      return

    if self.options.manualType == "raise-pen":
      self.penUp()

    elif self.options.manualType == "lower-pen":
      self.penDown()

    elif self.options.manualType == "version-check":
      strVersion = self.serialPort.query('$I\r')
      inkex.errormsg('Версия grbl:\n ' + strVersion)

    elif self.options.manualType == "grbl-command":
      strResponse = self.serialPort.query(self.options.grblCommand + '\r')
      inkex.errormsg('GRBL команда "' + self.options.grblCommand + '" ответ:\n ' + strResponse)
 # self.options.manualType is walk motor:
    else: 
      if self.options.manualType == "walk-y-motor":
        nDeltaX = 0
        nDeltaY = self.options.WalkDistance
      elif self.options.manualType == "walk-x-motor":
        nDeltaY = 0
        nDeltaX = self.options.WalkDistance
      else:
        return
      
      self.fSpeed = self.PenDownSpeed
        
      self.EnableMotors()
      self.fCurrX = self.svgLastKnownPosX_Old + chilmel_conf.StartPosX
      self.fCurrY = self.svgLastKnownPosY_Old + chilmel_conf.StartPosY
      self.ignoreLimits = True
      fX = self.fCurrX + nDeltaX
      fY = self.fCurrY + nDeltaY
      self.plotSegment(fX, fY)

  def plotDocument(self):
    '''Рисует SVG документ'''
    # парсим svg данные как набор линий и отправляем каждый из них на отрисовку

    if self.serialPort is None:
      return

    if (not self.getDocProps()):
      inkex.errormsg(gettext.gettext(
      'Этот документ не имеет допустимых размеров.\n' +
      'Размеры документа должны быть в ' +
      'миллиметрах (mm) или дюймах (in).'))
      return

    # Обработка окна просмотра
    viewbox = self.svg.get('viewBox')
    if viewbox:
      vinfo = viewbox.strip().replace(',', ' ').split(' ')
      Offset0 = -float(vinfo[0])
      Offset1 = -float(vinfo[1])
      
      if (vinfo[2] != 0) and (vinfo[3] != 0):
        sx = self.svgWidth / float(vinfo[2])
        sy = self.svgHeight / float(vinfo[3])
    else: 
      # Handle case of no viewbox provided. 
      # This can happen with imported documents in Inkscape.  
      sx = 1.0 / float(plot_utils.pxPerInch)
      sy = sx 
      Offset0 = 0.0
      Offset1 = 0.0
    Offset0 = 0.0
    Offset1 = 0.0
    self.svgTransform = Transform('scale(%f,%f) translate(%f,%f)' % (sx, sy,Offset0, Offset1)).matrix

    self.penUp() 
    self.EnableMotors()
    self.sCurrentLayerName = '(Not Set)'

    try: 
      self.recursivelyTraverseSvg(self.svg, self.svgTransform)
      self.penUp()   # Всегда начинаем с поднятной ручки

      # возврат домой после окончания рисованния
      if ((not self.bStopped) and (self.ptFirst)):
        self.xBoundsMin = chilmel_conf.StartPosX
        self.yBoundsMin = chilmel_conf.StartPosY
        fX = self.ptFirst[0]
        fY = self.ptFirst[1] 
        self.nodeCount = self.nodeTarget
        self.plotSegment(fX, fY)
        
      if (not self.bStopped): 
        if (self.options.mode == "plot") or (self.options.mode == "layers") or (self.options.mode == "resume"):
          self.svgLayer = 0
          self.svgNodeCount = 0
          self.svgLastPath = 0
          self.svgLastPathNC = 0
          self.svgLastKnownPosX = 0
          self.svgLastKnownPosY = 0
          self.svgPausedPosX = 0
          self.svgPausedPosY = 0
          # Очистить сохраненные данные о положении из файла SVG,
          # ЕСЛИ мы завершили рисование из режима рисования, слоя или возобновления(вкладки).
      if (self.warnOutOfBounds):
        inkex.errormsg(gettext.gettext('Warning: 4xiDraw movement was limited by its physical range of motion. If everything looks right, your document may have an error with its units or scaling. Contact technical support for help!'))

      if (self.options.reportTime):
        elapsed_time = time.time() - self.start_time
        m, s = divmod(elapsed_time, 60)
        h, m = divmod(m, 60)
        inkex.errormsg("Elapsed time: %d:%02d:%02d" % (h, m, s) + " (Hours, minutes, seconds)")
        downDist = self.penDownDistance / (self.stepsPerInch * sqrt(2))
        totDist = downDist + self.penUpDistance / (self.stepsPerInch * sqrt(2))
        inkex.errormsg("Length of path drawn: %1.3f inches." % downDist)
        inkex.errormsg("Total distance moved: %1.3f inches." % totDist)

    finally:
      pass

  def recursivelyTraverseSvg(self, aNodeList,
      matCurrent=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
      parent_visibility='visible'):
    """
    Рекурсивно обходим документ для отрсовки всех путей. Функция отслеживает составные
    преобразования которые должны быть применены к каждому пути. 

    Эта функция обрабатывает path, group, line, rect, polyline, polygon,
    circle, ellipse и использование клонирования элементов. Необрабатываемые
    элементы должны быть преобразованы в пути в Inkscape.
    """
    for node in aNodeList:
      # Игнорируем невидимые узлы
      v = node.get('visibility', parent_visibility)
      if v == 'inherit':
        v = parent_visibility
      if v == 'hidden' or v == 'collapse':
        pass

      # сначала применяем текущее преобразование матрицы к преобразованию этого узла
      matNew = Transform(matCurrent) * Transform(Transform(node.get("transform")).matrix)

      if node.tag == inkex.addNS('g', 'svg') or node.tag == 'g':

        if (node.get(inkex.addNS('groupmode', 'inkscape')) == 'layer'): 
          self.sCurrentLayerName = node.get(inkex.addNS('label', 'inkscape'))
          self.DoWePlotLayer(self.sCurrentLayerName)
          if not self.options.boundingBox:
            self.penUp()
        self.recursivelyTraverseSvg(node, matNew, parent_visibility=v)    

      elif node.tag == inkex.addNS('use', 'svg') or node.tag == 'use':

        # <use> тег ссылается на другой SVG тег

        refid = node.get(inkex.addNS('href', 'xlink'))
        if refid:
          path = '//*[@id="%s"]' % refid[1:]
          refnode = node.xpath(path)
          if refnode:
            x = float(node.get('x', '0'))
            y = float(node.get('y', '0'))
            if (x != 0) or (y != 0):
              matNew2 = composeTransform(matNew, parseTransform('translate(%f,%f)' % (x,y)))
            else:
              matNew2 = matNew
            v = node.get('visibility', v)
            self.recursivelyTraverseSvg(refnode, matNew2, parent_visibility=v)
          else:
            pass
        else:
          pass
      elif self.plotCurrentLayer: # Пропукаем последующие проверки тегов, если мы не рисуем этот слой.
        if node.tag == inkex.addNS('path', 'svg'):
          doWePlotThisPath = False 
          if (self.resumeMode): 
            if (self.pathcount < self.svgLastPath_Old): 
              self.pathcount += 1 
            elif (self.pathcount == self.svgLastPath_Old):               
              self.nodeCount =  self.svgLastPathNC_Old 
              doWePlotThisPath = True 
          else:
            doWePlotThisPath = True
          if (doWePlotThisPath):
            self.pathcount += 1
            self.plotPath(node, matNew)
          
        elif node.tag == inkex.addNS('rect', 'svg') or node.tag == 'rect':
  
          # Преобразование вручную
          #    <rect x="X" y="Y" width="W" height="H"/> 
          # в 
          #    <path d="MX,Y lW,0 l0,H l-W,0 z"/> 
          # То есть явно нарисовать три стороны прямоугольника и
          # четвертая сторона неявно

          doWePlotThisPath = False 
          if (self.resumeMode): 
            if (self.pathcount < self.svgLastPath_Old): 
              self.pathcount += 1 
            elif (self.pathcount == self.svgLastPath_Old): 
              self.nodeCount =  self.svgLastPathNC_Old
              doWePlotThisPath = True 
          else:
            doWePlotThisPath = True
          if (doWePlotThisPath):
            self.pathcount += 1
            # # Create a path with the outline of the rectangle
            newpath = etree.Element(inkex.addNS('path', 'svg'))
            x = float(node.get('x'))
            y = float(node.get('y'))
            w = float(node.get('width'))
            h = float(node.get('height'))
            s = node.get('style')
            if s:
              newpath.set('style', s)
            t = node.get('transform')
            if t:
              newpath.set('transform', t)
            a = []
            AppendCommand(a, 'M ', [x, y])
            AppendCommand(a, ' l ', [w, 0])
            AppendCommand(a, ' l ', [0, h])
            AppendCommand(a, ' l ', [-w, 0])
            AppendCommand(a, ' Z', [])
            newpath.set('d', str(Path(a)))
            self.plotPath(newpath, matNew)
            
        elif node.tag == inkex.addNS('line', 'svg') or node.tag == 'line':
  
          # Преобразуем
          #
          #   <line x1="X1" y1="Y1" x2="X2" y2="Y2/>
          #
          # в
          #
          #   <path d="MX1,Y1 LX2,Y2"/>
  
  
          doWePlotThisPath = False 
          if (self.resumeMode): 
            if (self.pathcount < self.svgLastPath_Old): 
              self.pathcount += 1 
            elif (self.pathcount == self.svgLastPath_Old): 
              self.nodeCount =  self.svgLastPathNC_Old
              doWePlotThisPath = True 
          else:
            doWePlotThisPath = True
          if (doWePlotThisPath):
            self.pathcount += 1
            # Создаем путь, который будет содержать линию
            newpath = etree.Element(inkex.addNS('path', 'svg'))
            x1 = float(node.get('x1'))
            y1 = float(node.get('y1'))
            x2 = float(node.get('x2'))
            y2 = float(node.get('y2'))
            s = node.get('style')
            if s:
              newpath.set('style', s)
            t = node.get('transform')
            if t:
              newpath.set('transform', t)
            a = []
            AppendCommand(a, 'M ', [x1, y1])
            AppendCommand(a, ' L ', [x2, y2])
            newpath.set('d', str(Path(a)))
            self.plotPath(newpath, matNew)
            
  
        elif node.tag == inkex.addNS('polyline', 'svg') or node.tag == 'polyline':
  
          # Преобразуем
          #  <polyline points="x1,y1 x2,y2 x3,y3 [...]"/> 
          # В 
          #   <path d="Mx1,y1 Lx2,y2 Lx3,y3 [...]"/> 
          # Примечание: мы игнорируем полилинии без точек
  
          pl = node.get('points', '').strip()
          if pl == '':
            pass
          
          doWePlotThisPath = False 
          if (self.resumeMode): 
            if (self.pathcount < self.svgLastPath_Old): 
              self.pathcount += 1 
            elif (self.pathcount == self.svgLastPath_Old): 
              self.nodeCount =  self.svgLastPathNC_Old  
              doWePlotThisPath = True 
          else:
            doWePlotThisPath = True
          if (doWePlotThisPath):
            self.pathcount += 1
            
            pa = pl.split()
            if not len(pa):
              pass
            d = "M " + pa[0]
            for i in range(1, len(pa)):
              d += " L " + pa[i]
            newpath = etree.Element(inkex.addNS('path', 'svg'))
            newpath.set('d', d);
            s = node.get('style')
            if s:
              newpath.set('style', s)
            t = node.get('transform')
            if t:
              newpath.set('transform', t)
            self.plotPath(newpath, matNew)
  
        elif node.tag == inkex.addNS('polygon', 'svg') or node.tag == 'polygon':
  
          # Преобразуем 
          #  <polygon points="x1,y1 x2,y2 x3,y3 [...]"/> 
          # В 
          #   <path d="Mx1,y1 Lx2,y2 Lx3,y3 [...] Z"/> 
          # Примечание: мы игнорируем полилинии без точек
  
          pl = node.get('points', '').strip()
          if pl == '':
            pass
    
          doWePlotThisPath = False 
          if (self.resumeMode): 
            if (self.pathcount < self.svgLastPath_Old): 
              self.pathcount += 1 
            elif (self.pathcount == self.svgLastPath_Old): 
              self.nodeCount =  self.svgLastPathNC_Old
              doWePlotThisPath = True 
          else:
            doWePlotThisPath = True
          if (doWePlotThisPath):
            self.pathcount += 1
            
            pa = pl.split()
            if not len(pa):
              pass
            d = "M " + pa[0]
            for i in xrange(1, len(pa)):
              d += " L " + pa[i]
            d += " Z"
            newpath = etree.Element(inkex.addNS('path', 'svg'))
            newpath.set('d', d);
            s = node.get('style')
            if s:
              newpath.set('style', s)
            t = node.get('transform')
            if t:
              newpath.set('transform', t)
            self.plotPath(newpath, matNew)
            
        elif node.tag == inkex.addNS('ellipse', 'svg') or \
          node.tag == 'ellipse' or \
          node.tag == inkex.addNS('circle', 'svg') or \
          node.tag == 'circle':
  
            # Преобразуем круги и эллипсы в путь с двумя дугами по 180 градусов.
            # В общем случае (эллипс) преобразуем
            #   <ellipse rx="RX" ry="RY" cx="X" cy="Y"/> 
            # В 
            #   <path d="MX1,CY A RX,RY 0 1 0 X2,CY A RX,RY 0 1 0 X1,CY"/> 
            # где 
            #   X1 = CX - RX
            #   X2 = CX + RX 
            # Примечание: эллипсы или окружности со значением атрибута радиуса 0 игнорируются.
  
            if node.tag == inkex.addNS('ellipse', 'svg') or node.tag == 'ellipse':
              rx = float(node.get('rx', '0'))
              ry = float(node.get('ry', '0'))
            else:
              rx = float(node.get('r', '0'))
              ry = rx
            if rx == 0 or ry == 0:
              pass

            doWePlotThisPath = False 
            if (self.resumeMode): 
              if (self.pathcount < self.svgLastPath_Old): 
                self.pathcount += 1 
              elif (self.pathcount == self.svgLastPath_Old): 
                self.nodeCount =  self.svgLastPathNC_Old
                doWePlotThisPath = True 
            else:
              doWePlotThisPath = True
            if (doWePlotThisPath):
              self.pathcount += 1
            
              cx = float(node.get('cx', '0'))
              cy = float(node.get('cy', '0'))
              x1 = cx - rx
              x2 = cx + rx
              d = 'M %f,%f ' % (x1, cy) + \
                'A %f,%f ' % (rx, ry) + \
                '0 1 0 %f,%f ' % (x2, cy) + \
                'A %f,%f ' % (rx, ry) + \
                '0 1 0 %f,%f' % (x1, cy)
              newpath = etree.Element(inkex.addNS('path', 'svg'))
              newpath.set('d', d);
              s = node.get('style')
              if s:
                newpath.set('style', s)
              t = node.get('transform')
              if t:
                newpath.set('transform', t)
              self.plotPath(newpath, matNew)
              
                
        elif node.tag == inkex.addNS('metadata', 'svg') or node.tag == 'metadata':
          pass
        elif node.tag == inkex.addNS('defs', 'svg') or node.tag == 'defs':
          pass
        elif node.tag == inkex.addNS('namedview', 'sodipodi') or node.tag == 'namedview':
          pass
        elif node.tag == inkex.addNS('WCB', 'svg') or node.tag == 'WCB':
          pass
        elif node.tag == inkex.addNS('eggbot', 'svg') or node.tag == 'eggbot':
          pass      
        elif node.tag == inkex.addNS('title', 'svg') or node.tag == 'title':
          pass
        elif node.tag == inkex.addNS('desc', 'svg') or node.tag == 'desc':
          pass
        elif (node.tag == inkex.addNS('text', 'svg') or node.tag == 'text' or
          node.tag == inkex.addNS('flowRoot', 'svg') or node.tag == 'flowRoot'):
          if (not 'text' in self.warnings) and (self.plotCurrentLayer):
            inkex.errormsg(gettext.gettext('Примечание. Этот файл содержит обычный текст, найденный в \nслое с названием: "' + 
              self.sCurrentLayerName + '" .\n' +
              'Пожалуйста, преобразуйте текст в контуры перед рисованием,  \n' +
              'испольуйте Контур > Оконтурить объект. \n'))
            self.warnings['text'] = 1
          pass
        elif node.tag == inkex.addNS('image', 'svg') or node.tag == 'image':
          if (not 'image' in self.warnings) and (self.plotCurrentLayer):
            inkex.errormsg(gettext.gettext('Предупреждение: в слое "' + 
            self.sCurrentLayerName + '" невозможно рисовать растровые изображения; ' +
            'Пожалуйста, конвертируйте изображения в штриховые рисунки перед рисованием. ' +
            ' Используйте Контур > Векторизировать растр. '))
            self.warnings['image'] = 1
          pass
        elif node.tag == inkex.addNS('pattern', 'svg') or node.tag == 'pattern':
          pass
        elif node.tag == inkex.addNS('radialGradient', 'svg') or node.tag == 'radialGradient':
          # Similar to pattern
          pass
        elif node.tag == inkex.addNS('linearGradient', 'svg') or node.tag == 'linearGradient':
          # Similar in pattern
          pass
        elif node.tag == inkex.addNS('style', 'svg') or node.tag == 'style':ы
          pass
        elif node.tag == inkex.addNS('cursor', 'svg') or node.tag == 'cursor':
          pass
        elif node.tag == inkex.addNS('color-profile', 'svg') or node.tag == 'color-profile':
          pass
        elif not isinstance(node.tag, str):
          pass
        else:
          if (not str(node.tag) in self.warnings) and (self.plotCurrentLayer):
            t = str(node.tag).split('}')
            inkex.errormsg(gettext.gettext('Предупреждение: в слое "' + 
              self.sCurrentLayerName + '" не могу рисовать ' + str(t[-1]) +
              '> пожалуйса переведите объект в контур сначала.'))
            self.warnings[str(node.tag)] = 1
          pass
  


  def DoWePlotLayer(self, strLayerName):
    TempNumString = 'x'
    stringPos = 1 
    layerNameInt = -1
    layerMatch = False  
    if sys.version_info < (3,):
      CurrentLayerName = strLayerName.encode('ascii', 'ignore')  
    else:
      CurrentLayerName=str(strLayerName)    
    CurrentLayerName.lstrip 
    self.plotCurrentLayer = True 
  
    MaxLength = len(CurrentLayerName)
    if MaxLength > 0:
      if CurrentLayerName[0] == '%':
        self.plotCurrentLayer = False
      while stringPos <= MaxLength:
        LayerNameFragment = CurrentLayerName[:stringPos]
        if (LayerNameFragment.isdigit()):
          TempNumString = CurrentLayerName[:stringPos] 
          stringPos = stringPos + 1
        else:
          break

    if (self.PrintInLayersMode): 
      if (str.isdigit(TempNumString)):
        layerNameInt = int(float(TempNumString))
        if (self.svgLayer == layerNameInt):
          layerMatch = True 
        
      if (layerMatch == False):
        self.plotCurrentLayer = False

    if (self.plotCurrentLayer == True):
      self.LayersFoundToPlot = True

      oldPenDown = self.LayerPenDownPosition
      oldSpeed = self.LayerPenDownSpeed
        
      self.LayerOverridePenDownHeight = False
      self.LayerOverrideSpeed = False
      self.LayerPenDownPosition = -1
      self.LayerPenDownSpeed = -1

      if (stringPos > 0):
        stringPos = stringPos - 1

      if MaxLength > stringPos + 2:
        while stringPos <= MaxLength: 
          EscapeSequence = CurrentLayerName[stringPos:stringPos+2].lower()
          if (EscapeSequence == "+h") or (EscapeSequence == "+s"):
            paramStart = stringPos + 2
            stringPos = stringPos + 3
            TempNumString = 'x'
            if MaxLength > 0:
              while stringPos <= MaxLength:
                if str.isdigit(CurrentLayerName[paramStart:stringPos]):
                  TempNumString = CurrentLayerName[paramStart:stringPos]
                  stringPos = stringPos + 1
                else:
                  break
            if (str.isdigit(TempNumString)):
              parameterInt = int(float(TempNumString))
          
              if (EscapeSequence == "+h"):
                if ((parameterInt >= 0) and (parameterInt <= 100)):
                  self.LayerOverridePenDownHeight = True
                  self.LayerPenDownPosition = parameterInt
                
              if (EscapeSequence == "+s"):
                if ((parameterInt > 0) and (parameterInt <= 100)):
                  self.LayerOverrideSpeed = True
                  self.LayerPenDownSpeed = parameterInt
                  
            stringPos = paramStart + len(TempNumString)
          else:
            break
      
      if (self.LayerPenDownSpeed != oldSpeed):
        self.EnableMotors()

  def plotPath(self, path, matTransform):
    
    self.logDebug('plotPath: Enter')
    # превратить этот путь в кубический суперпуть (список Безье)...

    d = path.get('d')

    if len(Path(d).to_arrays()) == 0:
      self.logDebug('plotPath: Zero length')
      return

    if self.plotCurrentLayer:
      self.logDebug('plotPath: plotCurrentLayer')
      p = CubicSuperPath(Path(d))
      p = inkex.paths.CubicSuperPath(Path(p).transform(Transform(matTransform)))
      for sp in p:
      
        plot_utils.subdivideCubicPath(sp, 0.02 / self.options.smoothness)
        nIndex = 0

        singlePath = []
        if self.plotCurrentLayer:
          for csp in sp:
            if self.bStopped:
              return
            if (self.printPortrait):
              fX = float(csp[1][1])
              fY = (self.svgWidth) - float(csp[1][0])
            else:
              fX = float(csp[1][0])
              fY = float(csp[1][1])

            self.logDebug('plotPath: X %f Y %f' % (fX, fY))

            if nIndex == 0:
              if (plot_utils.distance(fX - self.fCurrX, fY - self.fCurrY) > chilmel_conf.MinGap):
                if not self.options.boundingBox:
                  self.penUp()
                self.plotSegment(fX, fY)
            elif nIndex == 1:
              if not self.options.boundingBox:
                self.penDown() 
            nIndex += 1

            singlePath.append([fX,fY])
  
          self.PlanTrajectory(singlePath)
  
      if (not self.bStopped):
        self.svgLastPath = self.pathcount
        self.svgLastPathNC = self.nodeCount   


  def PlanTrajectory(self, inputPath):
    
    spewTrajectoryDebugData = False
    
    if spewTrajectoryDebugData:
      self.logDebug('\nPlanTrajectory()\n')

    if self.bStopped:
      return
    if (self.fCurrX is None):
      return

    if (self.ignoreLimits == False):
      for xy in inputPath:
        xy[0], xBounded = plot_utils.checkLimits(xy[0], self.xBoundsMin, self.xBoundsMax)
        xy[1], yBounded = plot_utils.checkLimits(xy[1], self.yBoundsMin, self.yBoundsMax)
        if (xBounded or yBounded):
          self.warnOutOfBounds = True
              
    if (len(inputPath) < 3):
      if spewTrajectoryDebugData:
        self.logDebug('Drawing straight line, not a curve.')
      self.plotSegment(xy[0], xy[1])                
      return

    TrajLength = len(inputPath)

    if spewTrajectoryDebugData:
      for xy in inputPath:
        self.logDebug('x: %1.3f,  y: %1.3f' %(xy[0], xy[1]))
      self.logDebug('\nTrajLength: '+str(TrajLength) + '\n')

    if (self.virtualPenIsUp): 
      speedLimit = self.PenUpSpeed/self.stepsPerInch 
    else:   
      speedLimit = self.PenDownSpeed/self.stepsPerInch

    TrajDists = array('f')
    TrajVectors = []

    TrajDists.append(0.0)

    for i in xrange(1, TrajLength):
      tmpDist = plot_utils.distance(inputPath[i][0] - inputPath[i - 1][0],
                  inputPath[i][1] - inputPath[i - 1][1])
      TrajDists.append(tmpDist)
      
      if (tmpDist == 0):
        tmpDist = 1
      tmpX = (inputPath[i][0] - inputPath[i - 1][0]) / tmpDist
      tmpY = (inputPath[i][1] - inputPath[i - 1][1]) / tmpDist
      TrajVectors.append([tmpX, tmpY])

    if spewTrajectoryDebugData:
      for dist in TrajDists:
        self.logDebug('TrajDists: %1.3f' % dist)
      self.logDebug('\n')

    for i in xrange(1, TrajLength):
      self.plotSegment(inputPath[i][0], inputPath[i][1])

  def plotSegment(self, xDest, yDest):
    spewSegmentDebugData = True

    if spewSegmentDebugData:
      self.logDebug('\nPlotSegment(x = %1.2f, y = %1.2f) ' % (xDest, yDest))
      if self.resumeMode: 
        self.logDebug('resumeMode is active')

    if self.bStopped:
      self.logDebug('Stopped')
      return
    if (self.fCurrX is None):
      self.logDebug('No current position')
      return

    if (self.ignoreLimits == False):
      xDest, xBounded = plot_utils.checkLimits(xDest, self.xBoundsMin, self.xBoundsMax)
      yDest, yBounded = plot_utils.checkLimits(yDest, self.yBoundsMin, self.yBoundsMax)
      if (xBounded or yBounded):
        self.warnOutOfBounds = True

    self.logDebug('doAbsoluteMove(%f, %f)' % (xDest, yDest))
    if self.options.boundingBox:
      self.bb['minX'] = min(self.bb['minX'], xDest)
      self.bb['minY'] = min(self.bb['minY'], yDest)
      self.bb['maxX'] = max(self.bb['maxX'], xDest)
      self.bb['maxY'] = max(self.bb['maxY'], yDest)
    else:
      self.motion.doAbsoluteMove(xDest, yDest)
                
  def EnableMotors(self):
    if (self.LayerOverrideSpeed):
      LocalPenDownSpeed = self.LayerPenDownSpeed
    else: 
      LocalPenDownSpeed = self.options.penDownSpeed

    self.stepsPerInch = float(chilmel_conf.DPI_16X)            
    self.PenDownSpeed = LocalPenDownSpeed * chilmel_conf.SpeedScale / 110.0
    self.PenUpSpeed = self.options.penUpSpeed * chilmel_conf.SpeedScale / 110.0
    if (self.options.constSpeed):
      self.PenDownSpeed = self.PenDownSpeed / 3
    
    TestArray = array('i')
    if (TestArray.itemsize < 4):
      inkex.errormsg('Internal array data length error. Please contact technical support.')

  def penUp(self):
    self.virtualPenIsUp = True  
    if (not self.resumeMode) and (not self.bPenIsUp):
      if (self.LayerOverridePenDownHeight):
        penDownPos = self.LayerPenDownPosition
      else: 
        penDownPos = self.options.penDownPosition
      vDistance = float(self.options.penUpPosition - penDownPos)
      vTime = int ((1000.0 * vDistance) / self.options.penLiftRate)
      if (vTime < 0):
        vTime = -vTime
      vTime += self.options.penLiftDelay  
      if (vTime < 0):
        vTime = 0 
      self.motion.sendPenUp(vTime, self.options.penUpSpeed if self.options.applySpeed else None)    
      if (vTime > 50):
        if self.options.mode != "manual":
          time.sleep(float(vTime - 10)/1000.0)
      self.bPenIsUp = True

  def penDown(self):
    self.virtualPenIsUp = False 
    if (self.bPenIsUp != False):
      if ((not self.resumeMode) and (not self.bStopped)):
        if (self.LayerOverridePenDownHeight):
          penDownPos = self.LayerPenDownPosition
        else: 
          penDownPos = self.options.penDownPosition
        vDistance = float(self.options.penUpPosition - penDownPos)
        vTime = int ((1000.0 * vDistance) / self.options.penLowerRate)
        if (vTime < 0):
          vTime = -vTime
        vTime += self.options.penLowerDelay 
        if (vTime < 0):
          vTime = 0
        self.motion.sendPenDown(vTime, self.options.penDownSpeed if self.options.applySpeed else None)            
        if (vTime > 50):
          if self.options.mode != "manual":
            time.sleep(float(vTime - 10)/1000.0)
        self.bPenIsUp = False

  def getDocProps(self):
    self.svgHeight = plot_utils.getLengthInches(self, 'height')
    self.svgWidth = plot_utils.getLengthInches(self, 'width')
    if (self.options.autoRotate) and (self.svgHeight > self.svgWidth):
      self.printPortrait = True
    if (self.svgHeight == None) or (self.svgWidth == None):
      return False
    else:
      return True

e = ChilMelClass()
e.run()
