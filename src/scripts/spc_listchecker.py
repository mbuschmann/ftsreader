from __future__ import print_function, division
import os, sys, time
from PyQt5.QtGui import QIcon
from matplotlib.backends.qt_compat import QtCore, QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from ftsreader import ftsreader
import numpy as np

class Speccheck(QtWidgets.QMainWindow):
    def __init__(self, readlist, savepath):
        super().__init__()
        self.folder = os.path.abspath(folder)
        self.savepath = os.path.abspath(savepath)
        self.getlist()
        self.marklist = []
        #
        self.title = 'Spectra Checker'
        self.setWindowTitle(self.title)
        #
        self.quickplot=False
        #
        self.initUI()
        #
        self._update_canvas()
        #

    def initUI(self):
        self._main = QtWidgets.QWidget()
        self.setCentralWidget(self._main)
        self.gridlayout = QtWidgets.QGridLayout()
        self.gridlayout.setSpacing(10)
        self.setWindowTitle(self.title)
        left = 10
        top = 10
        width = 1000
        height = 800
        self.setGeometry(left,top,width,height)
        self.statusBar().showMessage('Loading')
        #
        mainMenu=self.menuBar()
        fileMenu=mainMenu.addMenu('File')
        #
        openButton = QtWidgets.QAction(QIcon('open24.png'), 'Open', self)
        openButton.setShortcut('Ctrl+O')
        openButton.setStatusTip('Open directory')
        openButton.triggered.connect(self.getfolder)
        fileMenu.addAction(openButton)
        #
        exitButton=QtWidgets.QAction(QIcon('exit24.png'), 'Exit', self)
        exitButton.setShortcut('Ctrl+Q')
        exitButton.setStatusTip('Exit application')
        exitButton.triggered.connect(self.close)
        fileMenu.addAction(exitButton)
        #
        savebutton=QtWidgets.QPushButton('Save list',self)
        savebutton.setToolTip("Saving a list of all spectra marked with the 'mark spectrum' button as a textfile")
        self.gridlayout.addWidget(savebutton, 0, 4, 1 ,1, QtCore.Qt.AlignRight)
        savebutton.clicked.connect(self.savelist)
        #
        markbutton=QtWidgets.QPushButton('Mark spectrum',self)
        markbutton.setToolTip("Mark a spectrum to be put in the list")
        self.gridlayout.addWidget(markbutton, 0, 1, 1 ,1, QtCore.Qt.AlignRight)
        markbutton.clicked.connect(self.appendlist)
        #
        nextbutton=QtWidgets.QPushButton('Next',self)
        nextbutton.setToolTip("Go to the next spectrum in the list")
        self.gridlayout.addWidget(nextbutton, 0, 0, 1 ,1, QtCore.Qt.AlignRight)
        nextbutton.clicked.connect(self.nextspc)
        #
        checkBox = QtWidgets.QCheckBox("reduced plot")
        if self.quickplot: checkBox.toggle()
        checkBox.stateChanged.connect(self.setquickplot)
        self.gridlayout.addWidget(checkBox, 0, 3, 1 ,1, QtCore.Qt.AlignRight)
        #
        ##matplotlib integration from:
        ##https://matplotlib.org/gallery/user_interfaces/embedding_in_qt_sgskip.html#sphx-glr-gallery-user-interfaces-embedding-in-qt-sgskip-py
        self.dynamic_canvas = FigureCanvas(Figure(figsize=(6, 5)))
        self.gridlayout.addWidget(self.dynamic_canvas, 1,0,4,3)
        self.addToolBar(QtCore.Qt.BottomToolBarArea, NavigationToolbar(self.dynamic_canvas, self))
        self._dynamic_ax1, self._dynamic_ax2 = self.dynamic_canvas.figure.subplots(2)
        #
        self.dirlistwidget = QtWidgets.QListWidget()
        self.make_listwidget()
        #import ipdb; ipdb.set_trace()
        self.dirlistwidget.itemClicked.connect(self.listclick)
        self.gridlayout.addWidget(self.dirlistwidget, 1,3,3,2, QtCore.Qt.AlignRight)
        self._main.setLayout(self.gridlayout)
        self.show()

    def appendlist(self):
        self.marklist.append(self.filename)
        #import ipdb; ipdb.set_trace()
        self.i = self.dirlist.index(self.filename)
        self.dirlist2[self.i] = self.dirlist[self.i]+'  marked'
        if self.i+1<=len(self.dirlist):
            self.i = self.i+1
            self.filename = self.dirlist[self.i]
            #self.dirlistwidget.setCurrentItem(i+1)
            self._update_canvas()
        else:
            print('End of file list reached')

    def nextspc(self):
        #import ipdb; ipdb.set_trace()
        if self.i+1<=len(self.dirlist):
            self.i = self.i+1
            self.filename = self.dirlist[self.i]
            #self.dirlistwidget.setCurrentItem(i+1)
            self._update_canvas()
        else:
            print('End of file list reached')

    def listclick(self, item):
        #print(item)
        #import ipdb; ipdb.set_trace()
        self.filename = item.text().replace('  checked', '').replace('  marked', '')
        self.i = self.dirlist.index(self.filename)
        self.dirlist2[self.i] = self.dirlist[self.i]+'  checked'
        item.setText(item.text()+'  checked')
        self._update_canvas()

    def make_listwidget(self):
        self.dirlistwidget.clear()
        self.dirlistwidget.setItemDelegate
        for item in self.dirlist2:
            item = QtWidgets.QListWidgetItem(item)
            self.dirlistwidget.addItem(item)

    def getlist(self):
        l = []
        for i in os.listdir(self.folder):
            if not i.startswith('.') and os.path.isfile(os.path.join(self.folder,i)):
                l.append(i)
            else: pass
        l.sort()
        self.dirlist = l
        self.dirlist2 = l.copy()
        #print(self.dirlist)
        self.i = 0
        self.filename = self.dirlist[self.i]

    def getfolder(self):
        self.folder = str(QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory"))
        print('Opening ', self.folder)
        self.getlist()
        self.dirlistwidget.clear()
        for item in self.dirlist:
            item = QtWidgets.QListWidgetItem(item)
            self.dirlistwidget.addItem(item)
        self._update_canvas()

    def setquickplot(self, state):
        if state == QtCore.Qt.Checked:
            self.quickplot=True
        else:
            self.quickplot=False
        self._update_canvas()

    def _update_canvas(self):
        #print('Plotting ', self.filename)
        self._dynamic_ax1.clear()
        self._dynamic_ax2.clear()
        self._dynamic_ax1.set_title(self.filename)
        o = ftsreader(os.path.join(self.folder,self.filename), getspc=True, getifg=True)
        try:
            sx = o.spcwvn
            sy = o.spc
            spc = True
        except:
            spc = False
        try:
            iy = o.ifg
            ifg = True
        except:
            ifg = False
        redstepi = 3#int(len(iy)/1000)
        redsteps = 5#int(len(sx)/1000)
        if self.quickplot:
            if ifg:
                self._dynamic_ax1.plot(iy[::redstepi], 'k-')
                self._dynamic_ax1.figure.canvas.draw()
            else:
                print(os.path.join(self.folder,self.filename), ' --> no Interferogram found')
            if spc:
                self._dynamic_ax2.plot(sx[::redsteps], sy[::redsteps], 'k-')
                self._dynamic_ax2.figure.canvas.draw()
            else:
                print(os.path.join(self.folder,self.filename), ' --> no Spectrum found')
        else:
            if ifg:
                self._dynamic_ax1.plot(iy, 'k-')
                self._dynamic_ax1.figure.canvas.draw()
            else:
                print(os.path.join(self.folder,self.filename), ' --> no Interferogram found')
            if spc:
                self._dynamic_ax2.plot(sx, sy, 'k-')
                self._dynamic_ax2.figure.canvas.draw()
            else:
                print(os.path.join(self.folder,self.filename), ' --> no Spectrum found')
        i = self.dirlist.index(self.filename)
        self.dirlist2[i] = self.dirlist[i]+'  checked'
        self.make_listwidget()

    #def updateprogressbar(self, s):
    #    self.statusBar().showMessage(s)

    def savelist(self):
        print('Saving list of good spectra to ', self.savepath)
        with open(self.savepath, 'w') as f:
            for i in self.marklist:
                f.write(i+'\n')

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    if len(sys.argv)==3:
        ex = Speccheck(sys.argv[1], './spc_list_selection'+time.strftime('%Y%m%d%H%M')+'.txt')
    else:
        print('Options:\n\t spc_listchecker.py ')
    sys.exit(app.exec_())
