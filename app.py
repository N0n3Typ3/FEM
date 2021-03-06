#! /usr/bin/python3
# coding: utf-8


"""GUI for Finite Elements Method."""


__author__ = "Ewen BRUN, Pierre HAON"
__email__ = "ewen.brun@ecam.fr"


import ast
import models
import xlsxwriter
from PyQt5 import uic
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMainWindow, QApplication, QProgressDialog, QFileDialog, QMessageBox, QCheckBox
from sqlalchemy import text
from db.fem import Materials, Sections
from matplotlib import pyplot as plt
from time import perf_counter


def listModels(models=models):
    """List models."""
    with open(models.__file__, 'r') as source:
        p = ast.parse(source.read())
    return [node.name for node in ast.walk(p) if isinstance(node, ast.ClassDef) and node.name != "Model"]


qtCreatorFile = "ui/mainwindow.ui"
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)


class App(QMainWindow, Ui_MainWindow):
    """Mainwindow."""

    def __init__(self):
        """Init."""
        QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)
        self.horizontalSliderElements.setVisible(False)
        self.labelLimit.setVisible(False)
        self.lineEditElements.setVisible(False)
        self.lineEditElements.setText("512")
        self.listWidget.addItems(listModels())
        self.model = models.Model()
        self.loadMaterials()
        self.loadSections()
        self.loadSectionImage()
        self._isUp2date = True
        self._showAgain = True

        self.dockWidget.topLevelChanged.connect(self.updateWindowSize)
        self.listWidget.currentTextChanged.connect(self.modelChanged)
        self.comboBoxMaterials.currentTextChanged.connect(self.materialChanged)
        self.comboBoxSections.currentTextChanged.connect(self.sectionChanged)
        self.comboBoxConditions.currentTextChanged.connect(self.conditionsChanged)
        self.comboBoxResults.currentTextChanged.connect(self.updateGraph)
        self.horizontalSliderElements.valueChanged.connect(self.elementsNumberChanged)
        self.pushButtonStartComputation.clicked.connect(self.compute)
        self.pushButtonSave.clicked.connect(self.saveFigure)
        self.pushButtonExcel.clicked.connect(self.saveExcel)
        self.pushButtonPlotMatrix.clicked.connect(self.plotMatrix)
        self.mpl.canvas.depassement.connect(self.depassement)
        self.initWatchDog()

    def initWatchDog(self):
        """Init watchdog to detect when parameter do change."""
        self.comboBoxMaterials.activated.connect(self.showRunAgain)
        self.comboBoxSections.activated.connect(self.showRunAgain)
        self.comboBoxConditions.activated.connect(self.showRunAgain)
        self.doubleSpinBoxTall.valueChanged.connect(self.showRunAgain)
        self.doubleSpinBoxWide.valueChanged.connect(self.showRunAgain)
        self.doubleSpinBoxThick.valueChanged.connect(self.showRunAgain)
        self.doubleSpinBoxEffort.valueChanged.connect(self.showRunAgain)
        self.doubleSpinBoxLenght.valueChanged.connect(self.showRunAgain)
        self.checkBoxReparti.stateChanged.connect(self.showRunAgain)
        self.horizontalSliderElements.sliderReleased.connect(self.showRunAgain)

    def updateWindowSize(self, onTop):
        """Update window size if dockWidget is on Top."""
        if onTop:
            self.resize(self.minimumSize())
        else:
            self.resize(self.maximumSize())

    def modelChanged(self):
        """Change model on selection."""
        self.labelSelectModel.setHidden(True)
        self.pushButtonPlotMatrix.setEnabled(True)
        self.groupBoxConditions.setEnabled(True)
        self.groupBoxElements.setEnabled(True)
        self.groupBoxComputation.setEnabled(True)
        self.pushButtonPlotMatrix.setEnabled(False)
        self.labelStatus1.setText("✅")
        self.model = eval(
            "models." + self.listWidget.currentItem().text() + '()')
        self.loadConditions()
        if self.model._effortsRepartis:
            self.checkBoxReparti.setEnabled(True)
            self.labelEffort.setText("Effort en N/m")
        else:
            self.checkBoxReparti.setChecked(False)
            self.checkBoxReparti.setEnabled(False)
            self.labelEffort.setText("Effort en N")

    def currentObject(self, Class, name):
        """Return currentObject from Class matching Name."""
        return self.model.session.query(Class).filter(Class.Name == name).first()

    def materialChanged(self):
        """Change material on selection."""
        self.model.material = self.currentObject(Materials, self.comboBoxMaterials.currentText())

    def sectionChanged(self):
        """Change section on selection."""
        self.model.section = self.currentObject(Sections, self.comboBoxSections.currentText())
        if self.model.section.has_thickness:
            self.labelThick.setDisabled(False)
            self.doubleSpinBoxThick.setDisabled(False)
        else:
            self.labelThick.setDisabled(True)
            self.doubleSpinBoxThick.setDisabled(True)
        self.loadSectionImage()

    def elementsNumberChanged(self):
        """Change in number of elements."""
        self.pushButtonPlotMatrix.setEnabled(False)
        self.lineEditElements.setText(
            str(int(2**(self.horizontalSliderElements.value()))))

    def conditionsChanged(self):
        """Change in initial conditions."""
        self.model.selected = self.comboBoxConditions.currentIndex()

    def queryAll(self, where):
        """Query all elements names in column."""
        return [i[0] for i in self.model.session.execute(text('select Name from %s' % where))]

    def loadMaterials(self):
        """Load materials from db."""
        self.comboBoxMaterials.addItems(self.queryAll("Materials"))

    def loadSections(self):
        """Load scetion names from db."""
        self.comboBoxSections.addItems(self.queryAll("Sections"))

    def loadConditions(self):
        """Load initial conditions."""
        self.labelLimit.setVisible(False)
        self.comboBoxConditions.clear()
        self.comboBoxConditions.addItems(self.model.types)

    def depassement(self):
        """Depassement de la limite elastique du materiau."""
        self.labelLimit.setVisible(True)

    def loadSectionImage(self):
        """Load image corresponding to section from db."""
        p = QPixmap()
        p.loadFromData(self.model.section.raw_Image)
        p = p.scaled(32, 32)
        self.labelSectionImage.setPixmap(p)
        self.labelSectionImage.resize(p.width(), p.height())
        self.labelSectionImage.show()

    def plotMatrix(self):
        """Plot rigidity matrix."""
        plt.ion()
        plt.close()
        plt.matshow(self.model.K())
        plt.show()

    def showRunAgain(self):
        """Show a message indicating to start again computation."""
        if self._isUp2date is True and self._showAgain:
            warning = QMessageBox(self)
            warning.setText("Attention\nLes parametres on changés, il faut relancer les calculs")
            warning.setIcon(QMessageBox.Warning)
            warning.setWindowTitle("Attention")
            checkBox = QCheckBox()
            checkBox.setText(" Ne plus me demander")
            warning.setCheckBox(checkBox)
            warning.exec_()
            self._showAgain = not checkBox.isChecked()
            self._isUp2date = False

    def saveFigure(self):
        """Save figure."""
        try:
            name = QFileDialog.getSaveFileName(self, 'Save File')
            if name[0] != "":
                self.mpl.canvas.fig.savefig(name[0], dpi=300)
        except BaseException:
            QMessageBox.warning(self, 'Avertissement',
                                'Le fichier n\'as pas pu etre enregistré')

    def saveExcel(self):
        """Save data under excel file."""
        try:
            name = QFileDialog.getSaveFileName(self, 'Save File')[0]
            if name != "":
                if '.xlsx' not in name:
                    name += '.xlsx'
                wk = xlsxwriter.Workbook(name)
                ws = wk.add_worksheet("Déplacements")
                bold = wk.add_format({'bold': True})
                ws.write(0, 0, "Noeuds", bold)
                ws.write(0, 1, "Efforts nodaux", bold)
                ws.write(0, 2, "Deplacement", bold)
                for line in range(1, self.model._nodes + 1):
                    ws.write(line, 0, line)
                    ws.write(line, 1, self.model._FR[line - 1])
                    ws.write(line, 2, self.model._U._array[(line - 1)*self.model._D])
                wk.close()
        except BaseException:
            QMessageBox.warning(self, 'Avertissement', 'Le fichier n\'as pas pu etre enregistré')

    def compute(self):
        """Compute."""
        diag = QProgressDialog(self)
        diag.setRange(0, 0)
        diag.setValue(0)
        diag.setModal(True)
        diag.setWindowTitle("Calcul en cours")
        diag.setLabelText("Resolution en cours...")
        diag.show()
        tm = perf_counter()
        self.model._lenght = self.doubleSpinBoxLenght.value()
        self.updateSection()
        self.model.elems(int(self.lineEditElements.text()))
        self.pushButtonPlotMatrix.setEnabled(True)
        diag.show()
        QApplication.processEvents()
        if self.model._effortsRepartis:
            self.model.solve(self.doubleSpinBoxEffort.value(), self.checkBoxReparti.isChecked())
        else:
            self.model.solve(self.doubleSpinBoxEffort.value())
        at = perf_counter()
        diag.reset()
        self.labelComputationInfo.setText("Temps de calcul %f s" % (at - tm))
        self.updateGraph()

    def updateGraph(self):
        """Update graphs."""
        self.mpl.canvas.graph(self.model, self.comboBoxResults.currentIndex())
        self._isUp2date = True

    def updateSection(self):
        """Update section dimensions."""
        self.model.section.h = self.doubleSpinBoxTall.value()
        self.model.section.b = self.doubleSpinBoxWide.value()
        self.model.section.e = self.doubleSpinBoxThick.value()
