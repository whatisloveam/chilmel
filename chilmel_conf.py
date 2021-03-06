# chilmel_conf.py
# Part of the chilmel driver for Inkscape

PenUpPos = 40			# Положение пера по умолчанию - вверх
PenDownPos = 0			# Положение пера по умолчанию в нажатом положении

applySpeed = True      # Следует ли применять скорости к GRBL для перемещения пера вверх и вниз
PenUpSpeed = 5000       # Скорость при поднятии пера (мм/мин)
PenDownSpeed = 1000     # Скорость при опущенном пере (мм/мин)

penLowerDelay = 0		# задержка (мс) для опускания пера перед следующим ходом
penLiftDelay = 0		# задержка (мс) для поднятия пера перед следующим ходом

penLiftRate = 150		# Скорость сервопривода подъема ручки по умолчанию
penLowerRate = 150		# Скорость сервопривода подъема ручки по умолчанию при опускании


autoRotate = False		# Автоматическая печать в портретном или альбомном режиме
constSpeed = False		# Используйте режим постоянной скорости, когда перо опущено
reportTime = True		# Докладывать о времени рисования
logSerial = False		# Вести журнал последовательной связи

smoothness = 10.0		# Сглаживание кривой (default: 10.0)
cornering = 10.0		# Коэффициент скорости прохождения поворотов (default: 10.0)

DefaultLayer = 1		# Слой inkscape по умолчанию при рисовании в режиме "layers"

fileOutput = False		# Если True: Выводит обновленное содержимое SVG на stdout.

# Значения размера страницы обычно изменять не нужно. Они в первую очередь влияют на точку обзора и центровку.
# Измеряется с шагом в пикселях страницы. Область печати по умолчанию для 4xiDraw составляет 300 x 218 мм

PageWidthIn = 11.81		# Ширина страницы по умолчанию в дюймах	300 mm = about 11.81 inches
PageHeightIn = 8.58		# Высота страницы по умолчанию в дюймах 218 mm = about 8.58 inches


# Разрешение машины: Используется для преобразования размера чертежа в шаги двигателя.

DPI_16X = 100*25.4		# DPI ("dots per inch") @ 16X microstepping.  Стандартное значение: 100 steps per mm.  

SpeedScale = 24950		# Максимальная (110%) скорость, в шагах в секунду.

StartPosX = 0			# положение парковки по X, в пикселях. Значение по умолчанию: 0
StartPosY = 0			# положение парковки по Y, в пикселях. Значение по умолчанию: 0


# Скорости ускорения и временные срезы управления движением:
AccelTime = .2			# Секунды ускорения для достижения полной скорости С ОПУЩЕННЫМ ПЕРОМ
AccelTimePU = .5		# Секунды ускорения для достижения полной скорости С ПОДНЯТЫМ ПЕРОМ.
AccelTimePUHR = .15		# Секунды ускорения для достижения полной скорости С поднятым ПЕРОМ в более медленном режиме с высоким разрешением.

TimeSlice = 0.025		# Интервал времени обновления двигателей в секундах.

# Пороговое расстояние короткого перемещения пера вверх, ниже которого мы используем более высокую скорость ускорения пера вниз.:
ShortThreshold = 1.0	# Пороговое расстояние (дюймы)

# По возможности пропускайте движения пера вверх, которые короче этого расстояния.:
MinGap = 0.010			# Пороговое расстояние (дюймы)
