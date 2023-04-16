import sys
import PyQt5.QtWidgets as QtWidgets
from PyQt5 import uic
from PyQt5 import QtGui, QtCore
from pathlib import Path
import subprocess
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
#from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from PIL import Image
import numpy as np

from libfun import load_audio_data, create_actions

plt.style.use(["ggplot", "dark_background", "fast"])

class ImageWorker(QtCore.QObject):
	progressed = QtCore.pyqtSignal(int)
	finished = QtCore.pyqtSignal()

	def pre(self):
		# the figure that will contain the plot
		dpi = mpl.rcParams["figure.dpi"]
		self.fig = Figure(figsize=(self.w/dpi, self.h/dpi), dpi=dpi, tight_layout=True)

		# adding the subplot
		self.plot = self.fig.add_subplot(111)

		# canvas to draw on
		self.canvas = FigureCanvas(self.fig)

	def post(self):
		self.progressed.emit(90)

		self.canvas.draw()

		w, h = self.canvas.get_width_height()
		ch = 4
		bytesPerLine = ch * w
		im = QtGui.QImage(self.canvas.buffer_rgba(), w, h, bytesPerLine, QtGui.QImage.Format_RGBA8888)
		self.img = QtGui.QPixmap(im)

		self.progressed.emit(100)

class LoadWorker(ImageWorker):
	done = QtCore.pyqtSignal(dict, QtGui.QPixmap)

	def __init__(self, size, fileName, data):
		super().__init__()
		self.w = size[0]
		self.h = size[1]
		self.fileName = fileName
		self.data = data

	def run(self):
		self.progressed.emit(5)

		self.pre()

		#TODO: Better progressbar

		if (self.fileName):
			audioFile = Path("tmp", self.fileName.name)
			audioFile.parent.mkdir(parents=True, exist_ok=True)

			# TODO: Try catch
			subprocess.check_call([
				"ffmpeg",
				"-y",
				"-i", self.fileName,
				"-ar", "48000",
				audioFile
			])

			self.progressed.emit(20)

			self.data = load_audio_data(audioFile)

			self.progressed.emit(50)


		if len(self.data) > 0:
			# plotting the graph
			self.plot.plot(self.data["pitch"], label="pitch", linewidth=.3)
			self.plot.plot(self.data["energy"], label="energy", linewidth=.3)
			self.plot.legend()

		self.post()

		self.done.emit(self.data, self.img)
		self.finished.emit()


class RenderWorker(ImageWorker):
	done = QtCore.pyqtSignal(QtGui.QPixmap)
	my_cmap = LinearSegmentedColormap.from_list("intensity",["w", "g", "orange", "r"], N=256)

	def __init__(self, size, data, energy_mult, pitch_offset, overflow, heatmap=True):
		super().__init__()
		self.w = size[0]
		self.h = size[1]
		self.data = data
		self.energy_mult = energy_mult
		self.pitch_offset = pitch_offset
		self.overflow = overflow
		self.heatmap = heatmap

	def speed(self, A, B):
		return (abs(B[1] - A[1]) / abs(B[0] - A[0])) / 500

	def run(self):
		self.pre()

		if len(self.data) > 0:
			self.progressed.emit(5)

			# plotting the graph
			result = create_actions(
				self.data, 
				energy_multiplier=self.energy_mult,
				pitch_range=self.pitch_offset,
				overflow=self.overflow
			)

			# plotting the graph
			X,Y = map(list, zip(*result))
			if (self.heatmap):
				points = np.array([X, Y]).T.reshape(-1, 1, 2)
				segments = np.concatenate([points[:-1], points[1:]], axis=1)

				colors = np.array([self.my_cmap(self.speed((X[i], Y[i]), (X[i+1], Y[i+1]))) for i in range(len(Y)-1)])

				lc = LineCollection(segments, colors=colors, linewidths=.5)
				self.plot.add_collection(lc)
				self.plot.autoscale()
			else:
				self.plot.plot(X,Y, linewidth=.5)

		self.post()

		self.done.emit(self.img)
		self.finished.emit()

class MainUi(QtWidgets.QMainWindow):
	resized = QtCore.pyqtSignal()

	def __init__(self):
		super(MainUi, self).__init__()
		uic.loadUi("dancerUI.ui", self)
		self.OOR = 0
		self.fileName = None
		self.data = {}

		self.babout = self.findChild(QtWidgets.QToolButton, "aboutButton")
		self.bload = self.findChild(QtWidgets.QToolButton, "mediaButton")
		self.babout.clicked.connect(self.baboutPressed)
		self.bload.clicked.connect(self.bloadPressed)
		self.pbat = self.findChild(QtWidgets.QProgressBar, "progressBar")
		self.pbat.setValue(0)

		self.ginput = self.findChild(QtWidgets.QGraphicsView, "audioInput")
		self.goutput = self.findChild(QtWidgets.QGraphicsView, "audioOutput")
		self.gsinput = QtWidgets.QGraphicsScene()
		self.gsoutput = QtWidgets.QGraphicsScene()
		self.ginput.setScene(self.gsinput)
		self.goutput.setScene(self.gsoutput)
		self.ginput.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
		self.ginput.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
		self.goutput.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
		self.goutput.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

		self.bbounce = self.findChild(QtWidgets.QRadioButton, "bounceButton")
		self.bcrop = self.findChild(QtWidgets.QRadioButton, "cropButton")
		self.bfold = self.findChild(QtWidgets.QRadioButton, "foldButton")
		self.bbounce.clicked.connect(self.bbouncePressed)
		self.bcrop.clicked.connect(self.bcropPressed)
		self.bfold.clicked.connect(self.bfoldPressed)

		self.spitch = self.findChild(QtWidgets.QSlider, "pitchSlider")
		self.senergy = self.findChild(QtWidgets.QSlider, "energySlider")
		self.spitch.setRange(-200,200)
		self.spitch.setValue(100)
		self.senergy.setRange(0,100)
		self.senergy.setValue(10)
		self.spitch.valueChanged.connect(self.LoadWorker)
		self.senergy.valueChanged.connect(self.LoadWorker)

		self.bfunscript = self.findChild(QtWidgets.QPushButton, "funscriptButton")
		self.bheatmap = self.findChild(QtWidgets.QPushButton, "heatmapButton")
		self.bfunscript.clicked.connect(self.bfunscriptPressed)
		self.bheatmap.clicked.connect(self.bheatmapPressed)

		self.__loadworker = QtCore.QThread()
		self.__renderworker = QtCore.QThread()

		self.resized.connect(self.LoadWorker)

		self.LoadWorker()

	def resizeEvent(self, event):
		self.resized.emit()
		return super(MainUi, self).resizeEvent(event)

	def baboutPressed(self):
		print("baboutPressed")

	def bbouncePressed(self):
		self.OOR = 1
		self.RenderWorker()

	def bcropPressed(self):
		self.OOR = 0
		self.RenderWorker()

	def bfoldPressed(self):
		self.OOR = 2
		self.RenderWorker()

	# TODO: Generalize these
	def __load_done(self, data, img):
		self.data = data
		self.RenderWorker()
		self.gsinput.clear()
		gfxPixItem = self.gsinput.addPixmap(img)
		self.ginput.fitInView(gfxPixItem)

	def __load_prog(self, val):
		self.pbat.setValue(val)

	def __load_thread(self):
		thread = QtCore.QThread()
		worker = LoadWorker(
			(
				self.ginput.width(),
				self.ginput.height()
			),
			self.fileName,
			self.data
		)
		self.fileName = None
		worker.moveToThread(thread)

		# this is essential when worker is in local scope!
		thread.worker = worker

		thread.started.connect(worker.run)
		worker.done.connect(self.__load_done)
		worker.progressed.connect(self.__load_prog)
		worker.finished.connect(thread.quit)

		return thread

	def LoadWorker(self):
		if not self.__loadworker.isRunning():
			self.__loadworker = self.__load_thread()
			self.__loadworker.start()

	def __render_done(self, img):
		self.gsoutput.clear()
		gfxPixItem = self.gsoutput.addPixmap(img)
		self.goutput.fitInView(gfxPixItem)

	def __render_prog(self, val):
		self.pbat.setValue(val)

	def __render_thread(self):
		thread = QtCore.QThread()
		worker = RenderWorker(
			(
				self.goutput.width(),
				self.goutput.height()
			),
			self.data,
			self.senergy.value()/10,
			self.spitch.value(),
			self.OOR
		)
		worker.moveToThread(thread)

		# this is essential when worker is in local scope!
		thread.worker = worker

		thread.started.connect(worker.run)
		worker.done.connect(self.__render_done)
		worker.progressed.connect(self.__render_prog)
		worker.finished.connect(thread.quit)

		return thread

	def RenderWorker(self):
		if not self.__renderworker.isRunning():
			self.__renderworker = self.__render_thread()
			self.__renderworker.start()

	def bloadPressed(self):
		options = QtWidgets.QFileDialog.Options()
		options |= QtWidgets.QFileDialog.DontUseNativeDialog
		fileName, _ = QtWidgets.QFileDialog.getOpenFileName(self,"QFileDialog.getOpenFileName()", "","All Files (*);;Python Files (*.py)", options=options)
		if fileName:
			self.fileName = Path(fileName)
			self.setWindowTitle(f"Video: {self.fileName.name}")
			self.LoadWorker()

	def bfunscriptPressed(self):
		print("bfunscriptPressed")

	def bheatmapPressed(self):
		print("bheatmapPressed")

if __name__ == "__main__":
	app = QtWidgets.QApplication(sys.argv)
	window = MainUi()
	window.show()
	sys.exit(app.exec_())