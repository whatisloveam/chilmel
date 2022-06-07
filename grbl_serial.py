# grbl_serial.py
# рутина работы с портами

import serial, time, sys, string
import inkex
import gettext
import datetime

def findPort():
    # Находим плату GRBL, подключенную к порту USB.
    try:
        from serial.tools.list_ports import comports
    except ImportError:
        comports = None
        return None
    if comports:
        comPortsList = list(comports())
        for port in comPortsList:
            desc = port[1].lower()
            isUsbSerial = "usb" in desc and "serial" in desc
            isArduino = "arduino" in desc or "acm" in desc

            if isUsbSerial or isArduino:
                return port[0]
    return None

def testPort(comPort):
    '''
    Возвращает объект SerialPort для первого порта в списке.
    Порт необходимо закрывать!
    '''
    if comPort is not None:
        try:
            serialPort = serial.Serial()
            serialPort.baudrate = 115200
            serialPort.timeout = 1.0
            serialPort.rts = False
            serialPort.dtr = True
            serialPort.port = comPort
            serialPort.open()
            time.sleep(2)
            
            # Открытие порта может сбросить плату и мы получим сообщение о версии
            # 
            # При открытии порта плата должна перезагрузиться, но это может не произойти.
            # Для фикса отправляем сигнал сброса '\x18' что должно вызвать сброс.
            # а ответом будут 2 сообщения о версии.
            # 
            # I'm making this conditional on Python3 because for all I know earlier versions act differently here. But it's
            # possible that this behaviuor may occur with others. If we make the code unconditional we potentially incur
            # 2 comms timeouts at 1 second each.
            
            nTryCount = 0
            returnedMessage = ''
            while (len(returnedMessage) == 0) and (nTryCount < 2):
                returnedMessage = serialPort.readline().decode().rstrip()
                nTryCount += 1
            if len(returnedMessage) != 0: # если пришел ответ сразу то возвращаем порт
                if returnedMessage.startswith('Grbl'):
                    return serialPort
            
            # если открытие порта не вызвало сброс, отправляем команду сброса
            serialPort.write(b'\x18')
            time.sleep(1)
            
            while True:
                strVersion = serialPort.readline()
                if len(strVersion) == 0:
                    break
                grblTarget = b'Grbl'
                if strVersion and strVersion.startswith(grblTarget): # если пришел ответ - возвращаем порт
                    return serialPort
            serialPort.close()
        except serial.SerialException:
            pass
        return None
    else:
        return None

# Возврат объекта GrblSerial
def openPort(doLog):
    foundPort = findPort()
    serialPort = testPort(foundPort)
    if serialPort:
        g = GrblSerial(serialPort, doLog)
        # режим абсолютного позиционирования
        g.command('G90\r')
        return g
    return None

def escaped(s):
    r = ''
    for c in s:
        if ord(c) < 32:
            r = r + ('<%02X>' % ord(c))
        else:
            r = r + c
    return r


class GrblSerial(object):
    def __init__(self, port, doLog):
        self.port = port
        self.doLog = doLog

    # для вывода данных в отдельный файл
    def log(self, type, text):
        ts = datetime.datetime.now()
        try:
            with open("chilmel-serial.log", "a") as myfile:
                myfile.write('--- %s\n%s\n%s\n' % (ts.isoformat(), type, escaped(text)))
        except:
            inkex.errormsg(gettext.gettext("Error logging serial data."))

    # закрытие порта
    def close(self):
        if self.port is not None:
            try:
                self.port.close()
            except serial.SerialException:
                pass

    # запись данных
    def write(self, data):
        if self.doLog:
            self.log('SEND', data)
        self.port.write(data.encode())

    # чтение порта до символа переноса строки
    def readline(self):
        data = self.port.readline().decode().rstrip()
        if self.doLog:
            self.log('RECV', data)
        return data
    
    #функция обработки запроса (запрос->ответ)
    def query(self, cmd):
        if (self.port is not None) and (cmd is not None):
            response = ''
            try:
                self.write(cmd)
                response = self.readline()
                nRetryCount = 0
                while (len(response) == 0) and (nRetryCount < 100):
                    if self.doLog:
                        self.log('QUERY', 'read %d' % nRetryCount)
                    response = self.readline()
                    nRetryCount += 1
                    
                # считываем ok
                extra = self.readline()
                while (len(extra) > 0 and extra != 'ok'):
                    if self.doLog:
                        self.log('QUERY', 'read extra: ' + extra)
                    response = response + '\r' + extra
                    extra = self.readline()
                if self.doLog:
                    self.log('QUERY', 'response is '+response)
            except serial.SerialException:
                inkex.errormsg(gettext.gettext("Error reading serial data."))
            return response
        else:
            return None

    def command(self, cmd):
        if (self.port is not None) and (cmd is not None):
            try:
                self.write(cmd)
                response = self.readline()
                nRetryCount = 0
                while (len(response) == 0) and (nRetryCount < 30):
                    # get new response to replace null response if necessary
                    response = self.readline()
                    nRetryCount += 1
                if 'ok' in response.strip():
                    return
                else:
                    if (response != ''):
                        inkex.errormsg('Error: неожиданый ответ Grbl.') 
                        inkex.errormsg('   Команда: ' + cmd.strip())
                        inkex.errormsg('   Ответ: ' + str(response.strip()))
                    else:
                        inkex.errormsg('GRBL Таймаут ответа от команды: %s)' % cmd.strip())
                        sys.exit()
            except:
                inkex.errormsg('Ошибка после команды: ' + cmd)
                sys.exit()

if __name__ == "__main__":

    serialPort = openPort(True)

    print('ver: '+serialPort.query('$I\r'))
