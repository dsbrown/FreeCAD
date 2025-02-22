# -*- coding: utf8 -*-

#***************************************************************************
#*                                                                         *
#*   Copyright (c) 2009 Yorik van Havre <yorik@uncreated.net>              *  
#*                                                                         *
#*   This program is free software; you can redistribute it and/or modify  *
#*   it under the terms of the GNU Lesser General Public License (LGPL)    *
#*   as published by the Free Software Foundation; either version 2 of     *
#*   the License, or (at your option) any later version.                   *
#*   for detail see the LICENCE text file.                                 *
#*                                                                         *
#*   This program is distributed in the hope that it will be useful,       *
#*   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
#*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
#*   GNU Library General Public License for more details.                  *
#*                                                                         *
#*   You should have received a copy of the GNU Library General Public     *
#*   License along with this program; if not, write to the Free Software   *
#*   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
#*   USA                                                                   *
#*                                                                         *
#***************************************************************************

__title__="FreeCAD Draft Workbench - GUI part"
__author__ = "Yorik van Havre <yorik@uncreated.net>"
__url__ = ["http://www.freecadweb.org"]

## \defgroup DRAFTGUI DraftGui
#  \ingroup DRAFT
#
# GUI elements and utilities of the Draft workbench

'''
This is the GUI part of the Draft module.
Report to Draft.py for info
'''

import FreeCAD, FreeCADGui, os, Draft, sys, DraftVecUtils, math

try:
    from PySide import QtCore,QtGui,QtSvg
except ImportError:
    FreeCAD.Console.PrintMessage("Error: Python-pyside package must be installed on your system to use the Draft module.")

class todo:
    ''' static todo class, delays execution of functions.  Use todo.delay
    to schedule geometry manipulation that would crash coin if done in the
    event callback'''

    '''List of (function, argument) pairs to be executed by
    QtCore.QTimer.singleShot(0,doTodo).'''
    itinerary = []
    commitlist = []
    
    @staticmethod
    def doTasks():
        # print("debug: doing delayed tasks: commitlist: ",todo.commitlist," itinerary: ",todo.itinerary)
        for f, arg in todo.itinerary:
            try:
                # print("debug: executing",f)
                if arg:
                    f(arg)
                else:
                    f()
            except:
                wrn = "[Draft.todo.tasks] Unexpected error:", sys.exc_info()[0], "in ", f, "(", arg, ")"
                FreeCAD.Console.PrintWarning (wrn)
        todo.itinerary = []
        if todo.commitlist:
            for name,func in todo.commitlist:
                #print("debug: committing ",str(name))
                try:
                    name = str(name)
                    FreeCAD.ActiveDocument.openTransaction(name)
                    if isinstance(func,list):
                        for l in func:
                            FreeCADGui.doCommand(l)
                    else:
                        func()
                    FreeCAD.ActiveDocument.commitTransaction()
                except:
                    wrn = "[Draft.todo.commit] Unexpected error:", sys.exc_info()[0], "in ", f, "(", arg, ")"
                    FreeCAD.Console.PrintWarning (wrn)
            # restack Draft screen widgets after creation
            if hasattr(FreeCADGui,"Snapper"):
                FreeCADGui.Snapper.restack()
        todo.commitlist = []

    @staticmethod
    def delay (f, arg):
        # print("debug: delaying",f)
        if todo.itinerary == []:
            QtCore.QTimer.singleShot(0, todo.doTasks)
        todo.itinerary.append((f,arg))

    @staticmethod
    def delayCommit (cl):
        # print("debug: delaying commit",cl)
        QtCore.QTimer.singleShot(0, todo.doTasks)
        todo.commitlist = cl

def translate(context,text):
        "convenience function for Qt translator"
        return QtGui.QApplication.translate(context, text, None,
                                            QtGui.QApplication.UnicodeUTF8)

#---------------------------------------------------------------------------
# UNITS handling
#---------------------------------------------------------------------------
def getDefaultUnit(dim):
    '''return default Unit of Measure for a Dimension based on user preference
    Units Schema'''
    # only Length and Angle so far
    from FreeCAD import Units
    if dim == 'Length':
        qty = FreeCAD.Units.Quantity(1.0,FreeCAD.Units.Length)
        UOM = qty.getUserPreferred()[2]
    elif dim == 'Angle':
        qty = FreeCAD.Units.Quantity(1.0,FreeCAD.Units.Angle)
        UOM = qty.getUserPreferred()[2]
    else:
        UOM = "xx"
    return UOM
 
def makeFormatSpec(decimals=4,dim='Length'):
    ''' return a % format spec with specified decimals for a specified 
    dimension based on on user preference Units Schema'''
    if dim == 'Length':
        fmtSpec = "%." + str(decimals) + "f "+ getDefaultUnit('Length')
    elif dim == 'Angle':
        fmtSpec = "%." + str(decimals) + "f "+ getDefaultUnit('Angle')
    else:
        fmtSpec = "%." + str(decimals) + "f " + "??"
    return fmtSpec

def displayExternal(internValue,decimals=4,dim='Length',showUnit=True):
    '''return an internal value (ie mm) Length or Angle converted for display according 
    to Units Schema in use.'''
    from FreeCAD import Units

    if dim == 'Length':
        qty = FreeCAD.Units.Quantity(internValue,FreeCAD.Units.Length)
        pref = qty.getUserPreferred()
        conversion = pref[1]
        uom = pref[2]
    elif dim == 'Angle':
        qty = FreeCAD.Units.Quantity(internValue,FreeCAD.Units.Angle)
        pref=qty.getUserPreferred()
        conversion = pref[1]
        uom = pref[2]
    else:
        conversion = 1.0
        uom = "??"
    if not showUnit:
        uom = ""
    fmt = "{0:."+ str(decimals) + "f} "+ uom
    displayExt = fmt.format(float(internValue) / float(conversion))
    displayExt = displayExt.replace(".",QtCore.QLocale().decimalPoint())
    return displayExt

#---------------------------------------------------------------------------
# Customized widgets
#---------------------------------------------------------------------------

class DraftDockWidget(QtGui.QWidget):
    "custom Widget that emits a resized() signal when resized"
    def __init__(self,parent = None):
        QtGui.QWidget.__init__(self,parent)
    def resizeEvent(self,event):
        self.emit(QtCore.SIGNAL("resized()"))
    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.LanguageChange:
            self.emit(QtCore.SIGNAL("retranslate()"))
        else:
            QtGui.QWidget.changeEvent(self,event)
                        
class DraftLineEdit(QtGui.QLineEdit):
    "custom QLineEdit widget that has the power to catch Escape keypress"
    def __init__(self, parent=None):
        QtGui.QLineEdit.__init__(self, parent)
    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.emit(QtCore.SIGNAL("escaped()"))
        elif event.key() == QtCore.Qt.Key_Up:
            self.emit(QtCore.SIGNAL("up()"))
        elif event.key() == QtCore.Qt.Key_Down:
            self.emit(QtCore.SIGNAL("down()"))
        elif (event.key() == QtCore.Qt.Key_Z) and (int(event.modifiers()) == QtCore.Qt.ControlModifier):
            self.emit(QtCore.SIGNAL("undo()"))
        else:
            QtGui.QLineEdit.keyPressEvent(self, event)

class DraftTaskPanel:
    def __init__(self,widget,extra=None):
        if extra:
            if isinstance(extra,list):
                self.form = [widget] + extra
            else:
                self.form = [widget,extra]
        else:
            self.form = widget
    def getStandardButtons(self):
        return int(QtGui.QDialogButtonBox.Close)
    def accept(self):
        FreeCADGui.ActiveDocument.resetEdit()
        return True
    def reject(self):
        FreeCADGui.draftToolBar.isTaskOn = False
        FreeCADGui.draftToolBar.escape()
        FreeCADGui.ActiveDocument.resetEdit()
        return True

class DraftToolBar:
    "main draft Toolbar"
    def __init__(self):
        self.tray = None
        self.sourceCmd = None
        self.cancel = None
        self.pointcallback = None
        self.taskmode = Draft.getParam("UiMode",1)
        #print("taskmode: ",str(self.taskmode))
        self.paramcolor = Draft.getParam("color",255)>>8
        self.color = QtGui.QColor(self.paramcolor)
        self.facecolor = QtGui.QColor(204,204,204)
        self.linewidth = Draft.getParam("linewidth",2)
        self.fontsize = Draft.getParam("textheight",0.20)
        self.paramconstr = Draft.getParam("constructioncolor",746455039)>>8
        self.constrMode = False
        self.continueMode = False
        self.relativeMode = True
        self.state = None
        self.textbuffer = []
        self.crossedViews = []
        self.isTaskOn = False
        self.fillmode = Draft.getParam("fillmode",False)
        self.mask = None
        self.alock = False
        self.DECIMALS = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Units").GetInt("Decimals",2)
        self.FORMAT = makeFormatSpec(self.DECIMALS,'Length')
        self.AFORMAT = makeFormatSpec(self.DECIMALS,'Angle')
        self.uiloader = FreeCADGui.UiLoader()
        
        if self.taskmode:
            # add only a dummy widget, since widgets are created on demand
            self.baseWidget = QtGui.QWidget()
            self.tray = QtGui.QToolBar(None)
            self.tray.setObjectName("Draft tray")
            self.tray.setWindowTitle("Draft tray")
            self.toptray = self.tray
            self.bottomtray = self.tray
            self.setupTray()
            self.setupStyle()
            mw = FreeCADGui.getMainWindow()
            mw.addToolBar(self.tray)
            self.tray.setParent(mw)
            self.tray.show()

        else:
            # create the draft Toolbar                
            self.draftWidget = QtGui.QDockWidget()
            self.baseWidget = DraftDockWidget()
            self.draftWidget.setObjectName("draftToolbar")
            self.draftWidget.setTitleBarWidget(self.baseWidget)
            self.draftWidget.setWindowTitle(translate("draft", "Draft Command Bar"))
            self.mw = FreeCADGui.getMainWindow()
            self.mw.addDockWidget(QtCore.Qt.TopDockWidgetArea,self.draftWidget)
            self.draftWidget.setVisible(False)
            self.draftWidget.toggleViewAction().setVisible(False)                               
            self.baseWidget.setObjectName("draftToolbar")
            self.layout = QtGui.QHBoxLayout(self.baseWidget)
            self.layout.setObjectName("layout")
            self.toptray = self.layout
            self.bottomtray = self.layout
            self.setupToolBar()
            self.setupTray()
            self.setupStyle()
            self.retranslateUi(self.baseWidget)
		
#---------------------------------------------------------------------------
# General UI setup
#---------------------------------------------------------------------------

    def _pushbutton (self,name, layout, hide=True, icon=None, width=66, checkable=False):
        p = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/General")
        bsize = p.GetInt("ToolbarIconSize",24)+2
        isize = p.GetInt("ToolbarIconSize",24)/3*2
        button = QtGui.QPushButton(self.baseWidget)
        button.setObjectName(name)
        button.setMaximumSize(QtCore.QSize(width,bsize))
        if hide:
            button.hide()
        if icon:
            button.setIcon(QtGui.QIcon(':/icons/'+icon+'.svg'))
            button.setIconSize(QtCore.QSize(isize, isize))
        if checkable:
            button.setCheckable(True)
            button.setChecked(False)
        layout.addWidget(button)
        return button

    def _label (self,name, layout, hide=True):
        label = QtGui.QLabel(self.baseWidget)
        label.setObjectName(name)
        if hide: label.hide()
        layout.addWidget(label)
        return label

    def _lineedit (self,name, layout, hide=True, width=None):
        p = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/General")
        bsize = p.GetInt("ToolbarIconSize",24)-2
        lineedit = DraftLineEdit(self.baseWidget)
        lineedit.setObjectName(name)
        if hide: lineedit.hide()
        if not width: width = 800
        lineedit.setMaximumSize(QtCore.QSize(width,bsize))
        layout.addWidget(lineedit)
        return lineedit

    def _inputfield (self,name, layout, hide=True, width=None):
        p = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/General")
        bsize = p.GetInt("ToolbarIconSize",24)-2
        inputfield = self.uiloader.createWidget("Gui::InputField")
        inputfield.setObjectName(name)
        if hide: inputfield.hide()
        if not width: width = 800
        inputfield.setMaximumSize(QtCore.QSize(width,bsize))
        layout.addWidget(inputfield)
        return inputfield

    def _spinbox (self,name, layout, val=None, vmax=None, hide=True, double=False, size=None):
        if double:
            sbox = QtGui.QDoubleSpinBox(self.baseWidget)
            sbox.setDecimals(FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Units").GetInt("Decimals",2))
        else:
            sbox = QtGui.QSpinBox(self.baseWidget)
        sbox.setObjectName(name)
        if val: sbox.setValue(val)
        if vmax: sbox.setMaximum(vmax)
        if size: sbox.setMaximumSize(QtCore.QSize(size[0],size[1]))
        if hide: sbox.hide()
        layout.addWidget(sbox)
        return sbox

    def _checkbox (self,name, layout, checked=True, hide=True):
        chk = QtGui.QCheckBox(self.baseWidget)
        chk.setChecked(checked)
        chk.setObjectName(name)
        if hide: chk.hide()
        layout.addWidget(chk)
        return chk

    def _combo (self,name,layout,hide=True):
        cb = QtGui.QComboBox(self.baseWidget)
        cb.setObjectName(name)
        if hide: cb.hide()
        layout.addWidget(cb)
                        
    def setupToolBar(self,task=False):
        "sets the draft toolbar up"
        
        # command

        self.promptlabel = self._label("promptlabel", self.layout, hide=task)
        self.cmdlabel = self._label("cmdlabel", self.layout, hide=task)
        boldtxt = QtGui.QFont()
        boldtxt.setWeight(75)
        boldtxt.setBold(True)
        self.cmdlabel.setFont(boldtxt)

        # subcommands

        self.addButton = self._pushbutton("addButton", self.layout, icon="Draft_AddPoint", width=22, checkable=True)
        self.delButton = self._pushbutton("delButton", self.layout, icon="Draft_DelPoint", width=22, checkable=True)
        self.sharpButton = self._pushbutton("sharpButton", self.layout, icon="Draft_BezSharpNode", width=22, checkable=True)
        self.tangentButton = self._pushbutton("tangentButton", self.layout, icon="Draft_BezTanNode", width=22, checkable=True)
        self.symmetricButton = self._pushbutton("symmetricButton", self.layout, icon="Draft_BezSymNode", width=22, checkable=True)

        # point

        xl = QtGui.QHBoxLayout()
        yl = QtGui.QHBoxLayout()
        zl = QtGui.QHBoxLayout()
        self.layout.addLayout(xl)
        self.layout.addLayout(yl)
        self.layout.addLayout(zl)
        self.labelx = self._label("labelx", xl)
        self.xValue = self._inputfield("xValue", xl) #width=60
        self.xValue.setText(self.FORMAT % 0)
        self.labely = self._label("labely", yl)
        self.yValue = self._inputfield("yValue", yl)
        self.yValue.setText(self.FORMAT % 0)
        self.labelz = self._label("labelz", zl)
        self.zValue = self._inputfield("zValue", zl)
        self.zValue.setText(self.FORMAT % 0)
        
        # text
        
        self.textValue = self._lineedit("textValue", self.layout)
        
        # additional line controls

        ll = QtGui.QHBoxLayout()
        al = QtGui.QHBoxLayout()
        self.layout.addLayout(ll)
        self.layout.addLayout(al)
        self.labellength = self._label("labellength", ll)
        self.lengthValue = self._inputfield("lengthValue", ll)
        self.lengthValue.setText(self.FORMAT % 0)
        self.labelangle = self._label("labelangle", al)
        self.angleLock = self._checkbox("angleLock",al,checked=self.alock)
        self.angleValue = self._inputfield("angleValue", al)
        self.angleValue.setText(self.AFORMAT % 0)

        # shapestring
        
        self.labelSSize = self._label("labelSize", self.layout)
        self.SSizeValue = self._inputfield("SSizeValue", self.layout)           #, width=60)      
        self.SSizeValue.setText(self.FORMAT % 1.0)
        self.labelSTrack = self._label("labelTracking", self.layout)
        self.STrackValue = self._inputfield("STrackValue", self.layout)         #, width=60)    
        self.STrackValue.setText(self.FORMAT % 0)
        self.labelSString = self._label("labelString", self.layout)
        self.SStringValue = self._lineedit("SStringValue", self.layout)      
        self.SStringValue.setText("")
        self.labelFFile = self._label("labelFFile", self.layout)
        self.FFileValue = self._lineedit("FFileValue", self.layout)
        self.chooserButton = self._pushbutton("chooserButton", self.layout, width=26)
        self.chooserButton.setText("...")
        self.SSize = 1
        self.STrack = 0 
 
        # options
        
        fl = QtGui.QHBoxLayout()
        self.layout.addLayout(fl) 
        self.numFacesLabel = self._label("numfaceslabel", fl)      
        self.numFaces = self._spinbox("numFaces", fl, 3)
        ol = QtGui.QHBoxLayout()
        self.layout.addLayout(ol)
        self.offsetLabel = self._label("offsetlabel", ol)
        self.offsetValue = self._inputfield("offsetValue", ol)
        self.offsetValue.setText(self.FORMAT % 0)
        rl = QtGui.QHBoxLayout()
        self.layout.addLayout(rl)
        self.labelRadius = self._label("labelRadius", rl)
        self.radiusValue = self._inputfield("radiusValue", rl)
        self.radiusValue.setText(self.FORMAT % 0)
        self.isRelative = self._checkbox("isRelative",self.layout,checked=self.relativeMode)
        self.hasFill = self._checkbox("hasFill",self.layout,checked=self.fillmode)
        self.continueCmd = self._checkbox("continueCmd",self.layout,checked=self.continueMode)
        self.occOffset = self._checkbox("occOffset",self.layout,checked=False)
        self.undoButton = self._pushbutton("undoButton", self.layout, icon='Draft_Rotate')
        self.finishButton = self._pushbutton("finishButton", self.layout, icon='Draft_Finish')
        self.closeButton = self._pushbutton("closeButton", self.layout, icon='Draft_Lock')
        self.wipeButton = self._pushbutton("wipeButton", self.layout, icon='Draft_Wipe')
        self.selectButton = self._pushbutton("selectButton", self.layout, icon='view-select')
        self.xyButton = self._pushbutton("xyButton", self.layout)
        self.xzButton = self._pushbutton("xzButton", self.layout)
        self.yzButton = self._pushbutton("yzButton", self.layout)
        self.currentViewButton = self._pushbutton("view", self.layout)
        self.resetPlaneButton = self._pushbutton("none", self.layout)
        self.isCopy = self._checkbox("isCopy",self.layout,checked=False)

        # spacer
        if not self.taskmode:
            spacerItem = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding,
                                           QtGui.QSizePolicy.Minimum)
        else:
            spacerItem = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum,
                                           QtGui.QSizePolicy.Expanding)
        self.layout.addItem(spacerItem)
        

        QtCore.QObject.connect(self.xValue,QtCore.SIGNAL("valueChanged(double)"),self.changeXValue)
        QtCore.QObject.connect(self.yValue,QtCore.SIGNAL("valueChanged(double)"),self.changeYValue)
        QtCore.QObject.connect(self.zValue,QtCore.SIGNAL("valueChanged(double)"),self.changeZValue)
        QtCore.QObject.connect(self.lengthValue,QtCore.SIGNAL("valueChanged(double)"),self.changeLengthValue)
        QtCore.QObject.connect(self.angleValue,QtCore.SIGNAL("valueChanged(double)"),self.changeAngleValue)
        QtCore.QObject.connect(self.angleLock,QtCore.SIGNAL("stateChanged(int)"),self.toggleAngle) 
        QtCore.QObject.connect(self.radiusValue,QtCore.SIGNAL("valueChanged(double)"),self.changeRadiusValue)
        QtCore.QObject.connect(self.offsetValue,QtCore.SIGNAL("valueChanged(double)"),self.changeOffsetValue)
        QtCore.QObject.connect(self.xValue,QtCore.SIGNAL("returnPressed()"),self.checkx)
        QtCore.QObject.connect(self.yValue,QtCore.SIGNAL("returnPressed()"),self.checky)
        QtCore.QObject.connect(self.lengthValue,QtCore.SIGNAL("returnPressed()"),self.checkangle)
        QtCore.QObject.connect(self.xValue,QtCore.SIGNAL("textEdited(QString)"),self.checkSpecialChars)
        QtCore.QObject.connect(self.yValue,QtCore.SIGNAL("textEdited(QString)"),self.checkSpecialChars)
        QtCore.QObject.connect(self.zValue,QtCore.SIGNAL("textEdited(QString)"),self.checkSpecialChars)
        QtCore.QObject.connect(self.radiusValue,QtCore.SIGNAL("textEdited(QString)"),self.checkSpecialChars)
        QtCore.QObject.connect(self.zValue,QtCore.SIGNAL("returnPressed()"),self.validatePoint)
        QtCore.QObject.connect(self.radiusValue,QtCore.SIGNAL("returnPressed()"),self.validatePoint)
        QtCore.QObject.connect(self.angleValue,QtCore.SIGNAL("returnPressed()"),self.validatePoint)
        QtCore.QObject.connect(self.textValue,QtCore.SIGNAL("textChanged(QString)"),self.storeCurrentText)
        QtCore.QObject.connect(self.textValue,QtCore.SIGNAL("returnPressed()"),self.sendText)
        #QtCore.QObject.connect(self.textValue,QtCore.SIGNAL("escaped()"),self.escape)
        QtCore.QObject.connect(self.textValue,QtCore.SIGNAL("down()"),self.sendText)
        QtCore.QObject.connect(self.textValue,QtCore.SIGNAL("up()"),self.lineUp)
        QtCore.QObject.connect(self.zValue,QtCore.SIGNAL("returnPressed()"),self.xValue.setFocus)
        QtCore.QObject.connect(self.zValue,QtCore.SIGNAL("returnPressed()"),self.xValue.selectAll)
        QtCore.QObject.connect(self.offsetValue,QtCore.SIGNAL("textEdited(QString)"),self.checkSpecialChars)
        QtCore.QObject.connect(self.offsetValue,QtCore.SIGNAL("returnPressed()"),self.validatePoint)
        QtCore.QObject.connect(self.addButton,QtCore.SIGNAL("toggled(bool)"),self.setAddMode)
        QtCore.QObject.connect(self.delButton,QtCore.SIGNAL("toggled(bool)"),self.setDelMode)
        QtCore.QObject.connect(self.sharpButton,QtCore.SIGNAL("toggled(bool)"),self.setSharpMode)
        QtCore.QObject.connect(self.tangentButton,QtCore.SIGNAL("toggled(bool)"),self.setTangentMode)
        QtCore.QObject.connect(self.symmetricButton,QtCore.SIGNAL("toggled(bool)"),self.setSymmetricMode)
        QtCore.QObject.connect(self.finishButton,QtCore.SIGNAL("pressed()"),self.finish)
        QtCore.QObject.connect(self.closeButton,QtCore.SIGNAL("pressed()"),self.closeLine)
        QtCore.QObject.connect(self.wipeButton,QtCore.SIGNAL("pressed()"),self.wipeLine)
        QtCore.QObject.connect(self.undoButton,QtCore.SIGNAL("pressed()"),self.undoSegment)
        QtCore.QObject.connect(self.selectButton,QtCore.SIGNAL("pressed()"),self.selectEdge)
        QtCore.QObject.connect(self.xyButton,QtCore.SIGNAL("clicked()"),self.selectXY)
        QtCore.QObject.connect(self.xzButton,QtCore.SIGNAL("clicked()"),self.selectXZ)
        QtCore.QObject.connect(self.yzButton,QtCore.SIGNAL("clicked()"),self.selectYZ)
        QtCore.QObject.connect(self.continueCmd,QtCore.SIGNAL("stateChanged(int)"),self.setContinue)               
        QtCore.QObject.connect(self.isRelative,QtCore.SIGNAL("stateChanged(int)"),self.setRelative)
        QtCore.QObject.connect(self.hasFill,QtCore.SIGNAL("stateChanged(int)"),self.setFill) 
        QtCore.QObject.connect(self.currentViewButton,QtCore.SIGNAL("clicked()"),self.selectCurrentView)
        QtCore.QObject.connect(self.resetPlaneButton,QtCore.SIGNAL("clicked()"),self.selectResetPlane)
        QtCore.QObject.connect(self.xValue,QtCore.SIGNAL("undo()"),self.undoSegment)
        QtCore.QObject.connect(self.yValue,QtCore.SIGNAL("undo()"),self.undoSegment)
        QtCore.QObject.connect(self.zValue,QtCore.SIGNAL("undo()"),self.undoSegment)
        QtCore.QObject.connect(self.baseWidget,QtCore.SIGNAL("resized()"),self.relocate)
        QtCore.QObject.connect(self.baseWidget,QtCore.SIGNAL("retranslate()"),self.retranslateUi)
        QtCore.QObject.connect(self.SSizeValue,QtCore.SIGNAL("valueChanged(double)"),self.changeSSizeValue)
        QtCore.QObject.connect(self.SSizeValue,QtCore.SIGNAL("returnPressed()"),self.validateSNumeric)
        QtCore.QObject.connect(self.STrackValue,QtCore.SIGNAL("valueChanged(double)"),self.changeSTrackValue)
        QtCore.QObject.connect(self.STrackValue,QtCore.SIGNAL("returnPressed()"),self.validateSNumeric)
        QtCore.QObject.connect(self.SStringValue,QtCore.SIGNAL("returnPressed()"),self.validateSString)
        QtCore.QObject.connect(self.chooserButton,QtCore.SIGNAL("pressed()"),self.pickFile)
        QtCore.QObject.connect(self.FFileValue,QtCore.SIGNAL("returnPressed()"),self.validateFile)
        
        # following lines can cause a crash and are not needed anymore when using the task panel
        # http://forum.freecadweb.org/viewtopic.php?f=3&t=6952
        #QtCore.QObject.connect(self.FFileValue,QtCore.SIGNAL("escaped()"),self.escape)
        #QtCore.QObject.connect(self.xValue,QtCore.SIGNAL("escaped()"),self.escape)
        #QtCore.QObject.connect(self.yValue,QtCore.SIGNAL("escaped()"),self.escape)
        #QtCore.QObject.connect(self.zValue,QtCore.SIGNAL("escaped()"),self.escape)
        #QtCore.QObject.connect(self.radiusValue,QtCore.SIGNAL("escaped()"),self.escape)
        #QtCore.QObject.connect(self.SSizeValue,QtCore.SIGNAL("escaped()"),self.escape)
        #QtCore.QObject.connect(self.STrackValue,QtCore.SIGNAL("escaped()"),self.escape)
        #QtCore.QObject.connect(self.SStringValue,QtCore.SIGNAL("escaped()"),self.escape)

        # if Ui changed to have Size & Track visible at same time, use this
        #QtCore.QObject.connect(self.SSizeValue,QtCore.SIGNAL("returnPressed()"),self.checkSSize)
        #QtCore.QObject.connect(self.STrackValue,QtCore.SIGNAL("returnPressed()"),self.checkSTrack)
        
    def setupTray(self):
        "sets draft tray buttons up"

        self.wplabel = self._pushbutton("wplabel", self.toptray, icon='Draft_SelectPlane',hide=False,width=120)
        defaultWP = Draft.getParam("defaultWP",0)
        if defaultWP == 1:
            self.wplabel.setText("Top")
        elif defaultWP == 2:
            self.wplabel.setText("Front")
        elif defaultWP == 3:
            self.wplabel.setText("Side")
        else:
            self.wplabel.setText("Auto")
        self.constrButton = self._pushbutton("constrButton", self.toptray, hide=False, icon='Draft_Construction',width=22, checkable=True)
        self.constrColor = QtGui.QColor(self.paramconstr)
        self.colorButton = self._pushbutton("colorButton",self.bottomtray, hide=False,width=22)
        self.colorPix = QtGui.QPixmap(16,16)
        self.colorPix.fill(self.color)
        self.colorButton.setIcon(QtGui.QIcon(self.colorPix))
        self.facecolorButton = self._pushbutton("facecolorButton",self.bottomtray, hide=False,width=22)
        self.facecolorPix = QtGui.QPixmap(16,16)
        self.facecolorPix.fill(self.facecolor)
        self.facecolorButton.setIcon(QtGui.QIcon(self.facecolorPix))
        self.widthButton = self._spinbox("widthButton", self.bottomtray, val=self.linewidth,hide=False,size=(50,22))
        self.widthButton.setSuffix("px")
        self.fontsizeButton = self._spinbox("fontsizeButton",self.bottomtray, val=self.fontsize,vmax=999, hide=False,double=True,size=(65,22))
        self.applyButton = self._pushbutton("applyButton", self.toptray, hide=False, icon='Draft_Apply',width=22)

        QtCore.QObject.connect(self.wplabel,QtCore.SIGNAL("pressed()"),self.selectplane)
        QtCore.QObject.connect(self.colorButton,QtCore.SIGNAL("pressed()"),self.getcol)
        QtCore.QObject.connect(self.facecolorButton,QtCore.SIGNAL("pressed()"),self.getfacecol)
        QtCore.QObject.connect(self.widthButton,QtCore.SIGNAL("valueChanged(int)"),self.setwidth)
        QtCore.QObject.connect(self.fontsizeButton,QtCore.SIGNAL("valueChanged(double)"),self.setfontsize)
        QtCore.QObject.connect(self.applyButton,QtCore.SIGNAL("pressed()"),self.apply)
        QtCore.QObject.connect(self.constrButton,QtCore.SIGNAL("toggled(bool)"),self.toggleConstrMode)

    def setupStyle(self):
        style = "#constrButton:Checked {background-color: "
        style += self.getDefaultColor("constr",rgb=True)+" } "
        style += "#addButton:Checked, #delButton:checked, "
        style += "#sharpButton:Checked, "
        style += "#tangentButton:Checked, #symmetricButton:checked {"
        style += "background-color: rgb(20,100,250) }"
        self.baseWidget.setStyleSheet(style)
        #if hasattr(self,"tray"):
        #    self.tray.setStyleSheet(style)


#---------------------------------------------------------------------------
# language tools
#---------------------------------------------------------------------------
				
    def retranslateUi(self, widget=None):
        self.promptlabel.setText(translate("draft", "active command:"))
        self.cmdlabel.setText(translate("draft", "None"))
        self.cmdlabel.setToolTip(translate("draft", "Active Draft command"))
        self.xValue.setToolTip(translate("draft", "X coordinate of next point"))
        self.labelx.setText(translate("draft", "X"))
        self.labely.setText(translate("draft", "Y"))
        self.labelz.setText(translate("draft", "Z"))
        self.yValue.setToolTip(translate("draft", "Y coordinate of next point"))
        self.zValue.setToolTip(translate("draft", "Z coordinate of next point"))
        self.labellength.setText(translate("draft", "Length"))
        self.labelangle.setText(translate("draft", "Angle"))
        self.lengthValue.setToolTip(translate("draft", "Length of current segment"))
        self.angleValue.setToolTip(translate("draft", "Angle of current segment"))
        #self.angleLock.setText(translate("draft", "&Lock"))
        self.angleLock.setToolTip(translate("draft", "Check this to lock the current angle (l)"))
        self.labelRadius.setText(translate("draft", "Radius"))
        self.radiusValue.setToolTip(translate("draft", "Radius of Circle"))
        self.isRelative.setText(translate("draft", "&Relative"))
        self.isRelative.setToolTip(translate("draft", "Coordinates relative to last point or absolute (SPACE)"))
        self.hasFill.setText(translate("draft", "F&illed"))
        self.hasFill.setToolTip(translate("draft", "Check this if the object should appear as filled, otherwise it will appear as wireframe (i)"))
        self.finishButton.setText(translate("draft", "&Finish"))
        self.finishButton.setToolTip(translate("draft", "Finishes the current drawing or editing operation (F)"))
        self.continueCmd.setToolTip(translate("draft", "If checked, command will not finish until you press the command button again"))
        self.continueCmd.setText(translate("draft", "Con&tinue"))
        self.occOffset.setToolTip(translate("draft", "If checked, an OCC-style offset will be performed instead of the classic offset"))
        self.occOffset.setText(translate("draft", "&OCC-style offset"))
        self.addButton.setToolTip(translate("draft", "Add points to the current object"))
        self.delButton.setToolTip(translate("draft", "Remove points from the current object"))
        self.sharpButton.setToolTip(translate("draft", "Make Bezier node sharp"))
        self.tangentButton.setToolTip(translate("draft", "Make Bezier node tangent"))
        self.symmetricButton.setToolTip(translate("draft", "Make Bezier node symmetric"))
        self.undoButton.setText(translate("draft", "&Undo"))
        self.undoButton.setToolTip(translate("draft", "Undo the last segment (CTRL+Z)"))
        self.closeButton.setText(translate("draft", "&Close"))
        self.closeButton.setToolTip(translate("draft", "Finishes and closes the current line (C)"))
        self.wipeButton.setText(translate("draft", "&Wipe"))
        self.wipeButton.setToolTip(translate("draft", "Wipes the existing segments of this line and starts again from the last point (W)"))
        self.selectButton.setText(translate("draft", "&Select edge"))
        self.selectButton.setToolTip(translate("draft", "Selects an existing edge to be measured by this dimension (E)"))
        self.numFacesLabel.setText(translate("draft", "Sides"))
        self.numFaces.setToolTip(translate("draft", "Number of sides"))
        self.offsetLabel.setText(translate("draft", "Offset"))
        self.xyButton.setText(translate("draft", "XY"))
        self.xyButton.setToolTip(translate("draft", "Select XY plane"))
        self.xzButton.setText(translate("draft", "XZ"))
        self.xzButton.setToolTip(translate("draft", "Select XZ plane"))
        self.yzButton.setText(translate("draft", "YZ"))
        self.yzButton.setToolTip(translate("draft", "Select YZ plane"))
        self.currentViewButton.setText(translate("draft", "View"))
        self.currentViewButton.setToolTip(translate("draft", "Select plane perpendicular to the current view"))
        self.resetPlaneButton.setText(translate("draft", "Auto"))
        self.resetPlaneButton.setToolTip(translate("draft", "Do not project points to a drawing plane"))
        self.isCopy.setText(translate("draft", "&Copy"))
        self.isCopy.setToolTip(translate("draft", "If checked, objects will be copied instead of moved (C)"))
        self.SStringValue.setToolTip(translate("draft", "Text string to draw"))
        self.labelSString.setText(translate("draft", "String"))
        self.SSizeValue.setToolTip(translate("draft", "Height of text"))
        self.labelSSize.setText(translate("draft", "Height"))
        self.STrackValue.setToolTip(translate("draft", "Intercharacter spacing"))
        self.labelSTrack.setText(translate("draft", "Tracking"))
        self.labelFFile.setText(translate("draft", "Full path to font file:"))
        self.chooserButton.setToolTip(translate("draft", "Open a FileChooser for font file"))
        
        # Update the maximum width of the push buttons
        maxwidth = 66 # that's the default
        pb = []
        for i in range(self.layout.count()):
            w = self.layout.itemAt(i).widget()
            if w != None and w.inherits('QPushButton'):
                pb.append(w)
        
        for i in pb:
            fm = QtGui.QFontMetrics(i.font())
            fw = fm.width(i.text())
            fw = max(fw, maxwidth)
        
        maxwidth = maxwidth + 16 +10 # add icon width and a margin
        for i in pb:
            i.setMaximumWidth(maxwidth)
        
        if (not self.taskmode) or self.tray:
            self.wplabel.setToolTip(translate("draft", "Set/unset a working plane"))
            self.colorButton.setToolTip(translate("draft", "Line Color"))
            self.facecolorButton.setToolTip(translate("draft", "Face Color"))
            self.widthButton.setToolTip(translate("draft", "Line Width"))
            self.fontsizeButton.setToolTip(translate("draft", "Font Size"))
            self.applyButton.setToolTip(translate("draft", "Apply to selected objects"))
            self.constrButton.setToolTip(translate("draft", "Toggles Construction Mode"))

#---------------------------------------------------------------------------
# Interface modes
#---------------------------------------------------------------------------

    def taskUi(self,title="Draft",extra=None,icon="Draft_Draft"):
        if self.taskmode:
            self.isTaskOn = True
            todo.delay(FreeCADGui.Control.closeDialog,None)
            self.baseWidget = QtGui.QWidget()
            self.layout = QtGui.QVBoxLayout(self.baseWidget)
            self.setupToolBar(task=True)
            self.retranslateUi(self.baseWidget)
            self.panel = DraftTaskPanel(self.baseWidget,extra)
            todo.delay(FreeCADGui.Control.showDialog,self.panel)
        else:
            # create a dummy task to block the UI during the works
            class dummy:
                "an empty dialog"
                def __init__(self,extra=None):
                    if extra:
                        if isinstance(extra,list):
                            self.form = extra
                        else:
                            self.form = [extra]
                def getStandardButtons(self):
                    return int(QtGui.QDialogButtonBox.Close)
                def accept(self):
                    FreeCADGui.ActiveDocument.resetEdit()
                    return True
                def reject(self):
                    FreeCADGui.draftToolBar.isTaskOn = False
                    FreeCADGui.draftToolBar.escape()
                    FreeCADGui.ActiveDocument.resetEdit()
                    return True
            if FreeCADGui.Control.activeDialog():
                FreeCADGui.Control.closeDialog()
            todo.delay(FreeCADGui.Control.showDialog,dummy(extra))
        self.setTitle(title)
        
    def redraw(self):
        "utility function that is performed after each clicked point"
        self.checkLocal()
                
    def selectPlaneUi(self):
        self.taskUi(translate("draft", "Select Plane"))
        self.xyButton.show()
        self.xzButton.show()
        self.yzButton.show()
        self.currentViewButton.show()
        self.resetPlaneButton.show()
        self.offsetLabel.show()
        self.offsetValue.show()
        
    def extraLineUi(self):
        '''shows length and angle controls'''
        self.labellength.show()
        self.lengthValue.show()
        self.labelangle.show()
        self.angleValue.show()
        self.angleLock.show()

    def hideXYZ(self):
        ''' turn off all the point entry widgets '''
        self.labelx.hide()
        self.labely.hide()
        self.labelz.hide()
        self.labellength.hide()
        self.labelangle.hide()
        self.xValue.hide()
        self.yValue.hide()
        self.zValue.hide()
        self.lengthValue.hide()
        self.angleValue.hide()
        self.angleLock.hide()

    def lineUi(self,title=None):
        if title:
            self.pointUi(title,icon="Draft_Line")
        else:
            self.pointUi(translate("draft", "Line"),icon="Draft_Line")
        self.extraLineUi()
        self.xValue.setEnabled(True)
        self.yValue.setEnabled(True)
        self.isRelative.show()
        self.undoButton.show()
        self.continueCmd.show()

    def wireUi(self,title=None):
        if title:
            self.pointUi(title)
        else:
            self.pointUi(translate("draft", "DWire"),icon="Draft_Wire")
        self.xValue.setEnabled(True)
        self.yValue.setEnabled(True)
        self.isRelative.show()
        self.hasFill.show()
        self.finishButton.show()
        self.closeButton.show()
        self.wipeButton.show()
        self.undoButton.show()
        self.continueCmd.show()
        
    def circleUi(self):
        self.pointUi(translate("draft", "Circle"),icon="Draft_Circle")
        self.continueCmd.show()
        self.labelx.setText(translate("draft", "Center X"))
        self.hasFill.show()

    def arcUi(self):
        self.pointUi(translate("draft", "Arc"),icon="Draft_Arc")
        self.labelx.setText(translate("draft", "Center X"))
        self.continueCmd.show()

    def pointUi(self,title=translate("draft","Point"),cancel=None,extra=None,getcoords=None,rel=False,icon="Draft_Draft"):
        if cancel: self.cancel = cancel
        if getcoords: self.pointcallback = getcoords
        self.taskUi(title,extra,icon)
        self.xValue.setEnabled(True)
        self.yValue.setEnabled(True)
        self.checkLocal()
        self.labelx.show()
        self.labely.show()
        self.labelz.show()
        self.xValue.show()
        self.yValue.show()
        self.zValue.show()
        if rel: self.isRelative.show()
        self.xValue.setFocus()
        self.xValue.selectAll()

    def extraUi(self):
        pass

    def offsetUi(self):
        self.taskUi(translate("draft","Offset"))
        self.radiusUi()
        self.isCopy.show()
        self.occOffset.show()
        self.labelRadius.setText(translate("draft","Distance"))
        self.radiusValue.setText(self.FORMAT % 0)
        self.radiusValue.setFocus()
        self.radiusValue.selectAll()

    def offUi(self):
        todo.delay(FreeCADGui.Control.closeDialog,None)
        self.cancel = None
        self.sourceCmd = None
        self.pointcallback = None
        self.mask = None
        if self.taskmode:
            self.isTaskOn = False
            self.baseWidget = QtGui.QWidget()
        else:
            self.setTitle(translate("draft", "None"))
            self.labelx.setText(translate("draft", "X"))
            self.hideXYZ()
            self.numFacesLabel.hide()
            self.numFaces.hide()
            self.isRelative.hide()
            self.hasFill.hide()
            self.finishButton.hide()
            self.addButton.hide()
            self.delButton.hide()
            self.sharpButton.hide()
            self.tangentButton.hide()
            self.symmetricButton.hide()
            self.undoButton.hide()
            self.closeButton.hide()
            self.wipeButton.hide()
            self.selectButton.hide()
            self.xyButton.hide()
            self.xzButton.hide()
            self.yzButton.hide()
            self.currentViewButton.hide()
            self.resetPlaneButton.hide()
            self.offsetLabel.hide()
            self.offsetValue.hide()
            self.labelRadius.hide()
            self.radiusValue.hide()
            self.isCopy.hide()
            self.textValue.hide()
            self.continueCmd.hide()
            self.occOffset.hide()
            self.labelSString.hide()
            self.SStringValue.hide()
            self.labelSSize.hide()
            self.SSizeValue.hide()
            self.labelSTrack.hide()
            self.STrackValue.hide()
            self.labelFFile.hide()
            self.FFileValue.hide()
            self.chooserButton.hide()
            
    def trimUi(self,title=translate("draft","Trim")):
        self.taskUi(title)
        self.radiusUi()
        self.labelRadius.setText(translate("draft","Distance"))
        self.radiusValue.setText(self.FORMAT % 0)
        self.radiusValue.setFocus()
        self.radiusValue.selectAll()

    def radiusUi(self):
        self.hideXYZ()
        self.labelRadius.setText(translate("draft", "Radius"))
        self.labelRadius.show()
        self.radiusValue.setText(self.FORMAT % 0)
        self.radiusValue.show()

    def textUi(self):
        self.hideXYZ()
        self.textValue.show()
        self.textValue.setText('')
        self.textValue.setFocus()
        self.textbuffer=[]
        self.textline=0
        self.continueCmd.show()

    def SSUi(self):                 
        ''' set up ui for ShapeString text entry '''
        self.hideXYZ()
        self.labelSString.show()
        self.SStringValue.show()
        self.SStringValue.setText('')
        self.SStringValue.setFocus()
        self.continueCmd.hide()

    def SSizeUi(self):
        ''' set up ui for ShapeString size entry '''
        self.labelSString.hide()
        self.SStringValue.hide()
        self.continueCmd.hide()
        self.labelSSize.show()
        self.SSizeValue.setText(self.FORMAT % 1.0)
        self.SSizeValue.show()
        self.SSizeValue.setFocus()

    def STrackUi(self):
        ''' set up ui for ShapeString tracking entry '''
        self.labelSSize.hide()
        self.SSizeValue.hide()
        self.labelSTrack.show()
        self.STrackValue.setText(self.FORMAT % 0)
        self.STrackValue.show()
        self.STrackValue.setFocus()
        
    def SFileUi(self):
        ''' set up UI for ShapeString font file selection '''
        self.labelSTrack.hide()
        self.STrackValue.hide()
        if not self.FFileValue.text():
            self.FFileValue.setText(Draft.getParam("FontFile",""))
        self.labelFFile.show()
        self.FFileValue.show()
        self.chooserButton.show()
        self.FFileValue.setFocus()
                
    def switchUi(self,store=True):
        if store:
            self.state = []
            self.state.append(self.labelx.isVisible())
            self.state.append(self.labely.isVisible())
            self.state.append(self.labelz.isVisible())
            self.state.append(self.xValue.isVisible())
            self.state.append(self.yValue.isVisible())
            self.state.append(self.zValue.isVisible())
            self.hideXYZ()
        else:
            if self.state:
                if self.state[0]:self.labelx.show()
                if self.state[1]:self.labely.show()
                if self.state[2]:self.labelz.show()
                if self.state[3]:self.xValue.show()
                if self.state[4]:self.yValue.show()
                if self.state[5]:self.zValue.show()
                self.state = None

    def setTitle(self,title,icon="Draft_Draft"):
        if self.taskmode:
            self.baseWidget.setWindowTitle(title)
            self.baseWidget.setWindowIcon(QtGui.QIcon(":/icons/"+icon+".svg"))
        else:
            self.cmdlabel.setText(title)

    def selectUi(self,extra=None,callback=None):
        if not self.taskmode:
            self.labelx.setText(translate("draft", "Pick Object"))
            self.labelx.show()
        self.makeDumbTask(extra,callback)

    def editUi(self, mode=None):
        self.taskUi(translate("draft", "Edit"))
        self.hideXYZ()
        self.numFaces.hide()
        self.isRelative.hide()
        self.hasFill.hide()
        self.addButton.show()
        self.delButton.show()
        if mode == 'BezCurve':
            self.sharpButton.show()
            self.tangentButton.show()
            self.symmetricButton.show()
        self.finishButton.show()
        self.closeButton.show()
        # always start Edit with buttons unchecked
        self.addButton.setChecked(False)
        self.delButton.setChecked(False)
        self.sharpButton.setChecked(False)
        self.tangentButton.setChecked(False)
        self.symmetricButton.setChecked(False)

    def extUi(self):
        self.hasFill.show()
        self.continueCmd.show()

    def modUi(self):
        self.isCopy.show()
        self.continueCmd.show()

    def vertUi(self,addmode=True):
        self.addButton.setChecked(addmode)
        self.delButton.setChecked(not(addmode))
        
    def checkLocal(self):
        "checks if x,y,z coords must be displayed as local or global"
        self.labelx.setText(translate("draft", "Global X"))
        self.labely.setText(translate("draft", "Global Y"))
        self.labelz.setText(translate("draft", "Global Z"))
        if hasattr(FreeCAD,"DraftWorkingPlane"):
            if not FreeCAD.DraftWorkingPlane.isGlobal():
                self.labelx.setText(translate("draft", "Local X"))
                self.labely.setText(translate("draft", "Local Y"))
                self.labelz.setText(translate("draft", "Local Z"))

    def setEditButtons(self,mode):
        self.addButton.setEnabled(mode)
        self.delButton.setEnabled(mode)

    def setBezEditButtons(self,mode):
        self.sharpButton.setEnabled(mode)
        self.tangentButton.setEnabled(mode)
        self.symmetricButton.setEnabled(mode)

    def setNextFocus(self):
        def isThere(widget):
            if widget.isEnabled() and widget.isVisible():
                return True
            else:
                return False
        if (not self.taskmode) or self.isTaskOn:
            if isThere(self.xValue):
                self.xValue.setFocus()
                self.xValue.selectAll()
            elif isThere(self.yValue):
                self.yValue.setFocus()
                self.yValue.selectAll()
            elif isThere(self.zValue):
                self.zValue.setFocus()
                self.zValue.selectAll()
            elif isThere(self.radiusValue):
                self.radiusValue.setFocus()
                self.radiusValue.selectAll()

    def setRelative(self,val=1):
        self.relativeMode = bool(val)
        if (not self.taskmode) or self.isTaskOn:
            self.isRelative.show()

    def relocate(self):
        "relocates the right-aligned buttons depending on the toolbar size"
        if self.baseWidget.geometry().width() < 400:
            self.layout.setDirection(QtGui.QBoxLayout.TopToBottom)
        else:
            self.layout.setDirection(QtGui.QBoxLayout.LeftToRight)

    def makeDumbTask(self,extra=None,callback=None):
        "create a dumb taskdialog to prevent deleting the temp object"
        class TaskPanel:
            def __init__(self,extra=None,callback=None):
                if extra:
                    self.form = [extra]
            def getStandardButtons(self):
                return int(QtGui.QDialogButtonBox.Close)
            def reject(self):
                if callback:
                    callback()
                return True
        FreeCADGui.Control.closeDialog()
        panel = TaskPanel(extra,callback)
        FreeCADGui.Control.showDialog(panel)

#---------------------------------------------------------------------------
# Processing functions
#---------------------------------------------------------------------------
					
    def getcol(self):
        "opens a color picker dialog"
        self.color=QtGui.QColorDialog.getColor()
        self.colorPix.fill(self.color)
        self.colorButton.setIcon(QtGui.QIcon(self.colorPix))
        if Draft.getParam("saveonexit",False):
            Draft.setParam("color",self.color.rgb()<<8)
        r = float(self.color.red()/255.0)
        g = float(self.color.green()/255.0)
        b = float(self.color.blue()/255.0)
        col = (r,g,b,0.0)
        for i in FreeCADGui.Selection.getSelection():
            if (i.TypeId == "App::Annotation"):
                i.ViewObject.TextColor=col
            else:
                if "LineColor" in i.ViewObject.PropertiesList:
                    i.ViewObject.LineColor = col
                if "PointColor" in i.ViewObject.PropertiesList:
                    i.ViewObject.PointColor = col

    def getfacecol(self):
        "opens a color picker dialog"
        self.facecolor=QtGui.QColorDialog.getColor()
        self.facecolorPix.fill(self.facecolor)
        self.facecolorButton.setIcon(QtGui.QIcon(self.facecolorPix))
        r = float(self.facecolor.red()/255.0)
        g = float(self.facecolor.green()/255.0)
        b = float(self.facecolor.blue()/255.0)
        col = (r,g,b,0.0)
        for i in FreeCADGui.Selection.getSelection():
            if "ShapeColor" in i.ViewObject.PropertiesList:
                i.ViewObject.ShapeColor = col
					
    def setwidth(self,val):
        self.linewidth = float(val)
        if Draft.getParam("saveonexit",False):
            Draft.setParam("linewidth",int(val))
        for i in FreeCADGui.Selection.getSelection():
            if "LineWidth" in i.ViewObject.PropertiesList:
                i.ViewObject.LineWidth = float(val)

    def setfontsize(self,val):
        self.fontsize = float(val)
        if Draft.getParam("saveonexit",False):
            Draft.setParam("textheight",float(val))
        for i in FreeCADGui.Selection.getSelection():
            if "FontSize" in i.ViewObject.PropertiesList:
                i.ViewObject.FontSize = float(val)

    def setContinue(self,val):
        self.continueMode = bool(val)

    def setFill(self,val):
        self.fillmode = bool(val)
        
    def apply(self):
        for i in FreeCADGui.Selection.getSelection():
            Draft.formatObject(i)	

    def checkx(self):
        if self.yValue.isEnabled():
            self.yValue.setFocus()
            self.yValue.selectAll()
        else:
            self.checky()

    def checky(self):
        if self.zValue.isEnabled():
            self.zValue.setFocus()
            self.zValue.selectAll()
        else:
            self.validatePoint()
            
    def checkangle(self):
        self.angleValue.setFocus()
        self.angleValue.selectAll()

    def validatePoint(self):
        "function for checking and sending numbers entered manually"
        if self.sourceCmd or self.pointcallback:
            if (self.labelRadius.isVisible()):
                try:
                    #rad=float(self.radiusValue.text())
                    rad = self.radius
                except ValueError:
                    pass
                else:
                    self.sourceCmd.numericRadius(rad)
            elif (self.offsetLabel.isVisible()):
                try:
                    #offset=float(self.offsetValue.text())
                    offset = self.offset
                except ValueError:
                    pass
                else:
                    self.sourceCmd.offsetHandler(offset)
            else:
                try:
                    #numx=float(self.xValue.text())
                    numx = self.x
                    #numy=float(self.yValue.text())
                    numy = self.y
                    #numz=float(self.zValue.text())
                    numz = self.z
                except:
                    pass
                else:
                    if self.pointcallback:
                        self.pointcallback(FreeCAD.Vector(numx,numy,numz),self.relativeMode)
                    else:
                        if self.relativeMode:
                            if self.sourceCmd.node:
                                if self.sourceCmd.featureName == "Rectangle":
                                    last = self.sourceCmd.node[0]
                                else:
                                    last = self.sourceCmd.node[-1]
                                #print("last:",last)
                                v = FreeCAD.Vector(numx,numy,numz)
                                #print("orig:",v)
                                if FreeCAD.DraftWorkingPlane:
                                    v = FreeCAD.Vector(numx,numy,numz)
                                    v = FreeCAD.DraftWorkingPlane.getGlobalRot(v)
                                    #print("rotated:",v)
                                numx = last.x + v.x
                                numy = last.y + v.y
                                numz = last.z + v.z
                        self.sourceCmd.numericInput(numx,numy,numz)

    def validateSNumeric(self):
        ''' send valid numeric parameters to ShapeString '''
        if self.sourceCmd: 
            if (self.labelSSize.isVisible()):
                try:
                    SSize=float(self.SSize)
                except ValueError:
                    FreeCAD.Console.PrintMessage(translate("draft", "Invalid Size value. Using 200.0."))                     
                    self.sourceCmd.numericSSize(200.0)
                else:
                    self.sourceCmd.numericSSize(SSize)
            elif (self.labelSTrack.isVisible()):
                try:
                    track=int(self.STrack)
                except ValueError:
                    FreeCAD.Console.PrintMessage(translate("draft", "Invalid Tracking value. Using 0."))                     
                    self.sourceCmd.numericSTrack(0)
                else:
                    self.sourceCmd.numericSTrack(track)

    def validateSString(self):
        ''' send a valid text string to ShapeString as unicode '''
        if self.sourceCmd: 
            if (self.labelSString.isVisible()):
                if self.SStringValue.text():
                    #print("debug: D_G DraftToolBar.validateSString type(SStringValue.text): "  str(type(self.SStringValue.text)))
                    #self.sourceCmd.validSString(str(self.SStringValue.text()))    # QString to QByteArray to PyString
                    self.sourceCmd.validSString(self.SStringValue.text())    # PySide returns Unicode from QString
                else:
                    FreeCAD.Console.PrintMessage(translate("draft", "Please enter a text string."))                     
              
                    
    def pickFile(self):
        ''' invoke a font file chooser dialog and send result to ShapeString to'''
        if self.sourceCmd: 
            if (self.chooserButton.isVisible()):
                try:
                    dialogCaption = translate("draft", "Select a Font file")
                    dialogDir = os.path.dirname(Draft.getParam("FontFile",)) # reasonable default?
                    dialogFilter = "Fonts (*.ttf *.pfb *.otf);;All files (*.*)"
                    fname = QtGui.QFileDialog.getOpenFileName(self.baseWidget,
                                                              dialogCaption, 
                                                              dialogDir,
                                                              dialogFilter)
                    # print(fname)
                    #fname = str(fname.toUtf8())                                 # QString to PyString
                    fname = fname[0].decode("utf8")
#                    print("debug: D_G DraftToolBar.pickFile type(fname): "  str(type(fname)))
                                                              
                except Exception as e:
                    FreeCAD.Console.PrintMessage("DraftGui.pickFile: unable to select a font file.")
                    print(type(e))
                    print(e.args)
                else:
                    if fname:
                        self.FFileValue.setText(fname)
                        self.sourceCmd.validFFile(fname)                      
                    else:
                        FreeCAD.Console.PrintMessage("DraftGui.pickFile: no file selected.")   # can this happen?
    
    def validateFile(self):
        ''' check and send font file parameter to ShapeString as unicode'''
        if self.sourceCmd: 
            if (self.labelFFile.isVisible()):
                if self.FFileValue.text():
                    self.sourceCmd.validFFile(self.FFileValue.text().decode("utf8"))       #QString to PyString
                else:
                    FreeCAD.Console.PrintMessage(translate("draft", "Please enter a font file."))                    


    def finish(self):
        "finish button action"
        if self.sourceCmd:
            self.sourceCmd.finish(False)
        if self.cancel:
            self.cancel()
            self.cancel = None
        FreeCADGui.ActiveDocument.resetEdit()

    def escape(self):
        "escapes the current command"
        self.continueMode = False
        if not self.taskmode:
            self.continueCmd.setChecked(False)
        self.finish()

    def closeLine(self):
        "close button action"
        self.sourceCmd.finish(True)
        FreeCADGui.ActiveDocument.resetEdit()

    def wipeLine(self):
        "wipes existing segments of a line"
        self.sourceCmd.wipe()
        
    def selectEdge(self):
        "allows the dimension command to select an edge"
        if hasattr(self.sourceCmd,"selectEdge"):
            self.sourceCmd.selectEdge()

    def selectXY(self):
        self.sourceCmd.selectHandler("XY")

    def selectXZ(self):
        self.sourceCmd.selectHandler("XZ")

    def selectYZ(self):
        self.sourceCmd.selectHandler("YZ")

    def selectCurrentView(self):
        self.sourceCmd.selectHandler("currentView")

    def selectResetPlane(self):
        self.sourceCmd.selectHandler("reset")

    def undoSegment(self):
        "undo last line segment"
        self.sourceCmd.undolast()

    def checkSpecialChars(self,txt):
        '''
        checks for special characters in the entered coords that mut be
        treated as shortcuts
        '''
        spec = False
        if txt.endswith(" ") or txt.endswith("r"):
            self.isRelative.setChecked(not self.isRelative.isChecked())
            self.relativeMode = self.isRelative.isChecked()
            spec = True
        elif txt.endswith("i"):
            if self.hasFill.isVisible():
                self.hasFill.setChecked(not self.hasFill.isChecked())
            spec = True
        elif txt.endswith("f"):
            if self.finishButton.isVisible():
                self.finish()
            spec = True
        elif txt.endswith("t"):
            self.toggleContinue()
            spec = True
        elif txt.endswith("w"):
            self.wipeLine()
            spec = True
        elif txt.endswith("e"):
            self.selectEdge()
            spec = True
        elif txt.endswith("s"):
            self.togglesnap()
            spec = True
        elif txt.endswith("["):
            self.toggleradius(1)
            spec = True
        elif txt.endswith("]"):
            self.toggleradius(-1)
            spec = True
        elif txt.endswith("x"):
            self.constrain("x")
            self.displayPoint()
            spec = True
        elif txt.endswith("y"):
            self.constrain("y")
            self.displayPoint()
            spec = True
        elif txt.endswith("z"):
            self.constrain("z")
            self.displayPoint()
            spec = True
        elif txt.endswith("l"):
            self.constrain("angle")
            self.displayPoint()
            spec = True
        elif txt.endswith("c"):
            if self.closeButton.isVisible():
                self.closeLine()
            elif self.isCopy.isVisible():
                self.isCopy.setChecked(not self.isCopy.isChecked())
            elif self.continueCmd.isVisible():
                self.continueCmd.setChecked(not self.continueCmd.isChecked())
            spec = True
        if spec:
            for i in [self.xValue,self.yValue,self.zValue]:
                if (i.property("text") == txt):
                    i.setProperty("text",txt[:-1])

    def storeCurrentText(self,qstr):
        self.currEditText = self.textValue.text()

    def setCurrentText(self,tstr):
        if (not self.taskmode) or (self.taskmode and self.isTaskOn):
            self.textValue.setText(tstr)
    
    def sendText(self):
        '''
        this function sends the entered text to the active draft command
        if enter has been pressed twice. Otherwise it blanks the line.
        '''
        if self.textline == len(self.textbuffer):
            if self.textline:
                if not self.currEditText:
                    self.sourceCmd.text=self.textbuffer
                    self.sourceCmd.createObject()
            self.textbuffer.append(self.currEditText)
            self.textline += 1
            self.setCurrentText('')
        elif self.textline < len(self.textbuffer):
            self.textbuffer[self.textline] = self.currEditText
            self.textline += 1
            if self.textline < len(self.textbuffer):
                self.setCurrentText(self.textbuffer[self.textline])
            else:
                self.setCurrentText('')

    def lineUp(self):
        "displays previous line in text editor"
        if self.textline:
            if self.textline == len(self.textbuffer):
                self.textbuffer.append(self.textValue.text())
                self.textline -= 1
                if self.textValue.text():
                    self.textValue.setText(self.textbuffer[self.textline])
            elif self.textline < len(self.textbuffer):
                self.textbuffer[self.textline] = self.textValue.text()
                self.textline -= 1
                self.textValue.setText(self.textbuffer[self.textline])

    def displayPoint(self, point=None, last=None, plane=None, mask=None):
        "this function displays the passed coords in the x, y, and z widgets"

        if (not self.taskmode) or self.isTaskOn:

            # get coords to display
            dp = None
            if point:
                dp = point
                if self.relativeMode and (last != None):
                    if plane:
                        dp = plane.getLocalRot(FreeCAD.Vector(point.x-last.x, point.y-last.y, point.z-last.z))
                    else:
                        dp = FreeCAD.Vector(point.x-last.x, point.y-last.y, point.z-last.z)
                elif plane:
                    dp = plane.getLocalCoords(point)

            # set widgets
            if self.mask in ['y','z']:
                self.xValue.setText(displayExternal(dp.x,self.DECIMALS,'Length'))
            else:
                if dp:
                    self.xValue.setText(displayExternal(dp.x,self.DECIMALS,'Length'))
            if self.mask in ['x','z']:
                self.yValue.setText(displayExternal(dp.y,self.DECIMALS,'Length'))
            else:
                if dp:
                    self.yValue.setText(displayExternal(dp.y,self.DECIMALS,'Length'))
            if self.mask in ['x','y']:
                self.zValue.setText(displayExternal(dp.z,self.DECIMALS,'Length'))
            else:
                if dp:
                    self.zValue.setText(displayExternal(dp.z,self.DECIMALS,'Length'))

            # set masks
            if (mask == "x") or (self.mask == "x"):
                self.xValue.setEnabled(True)
                self.yValue.setEnabled(False)
                self.zValue.setEnabled(False)
                self.xValue.setFocus()
                self.xValue.selectAll()
            elif (mask == "y") or (self.mask == "y"):
                self.xValue.setEnabled(False)
                self.yValue.setEnabled(True)
                self.zValue.setEnabled(False)
                self.yValue.setFocus()
                self.yValue.selectAll()
            elif (mask == "z") or (self.mask == "z"):
                self.xValue.setEnabled(False)
                self.yValue.setEnabled(False)
                self.zValue.setEnabled(True)
                self.zValue.setFocus()
                self.zValue.selectAll()
            else:
                self.xValue.setEnabled(True)
                self.yValue.setEnabled(True)
                self.zValue.setEnabled(True)
                self.xValue.setFocus()
                self.xValue.selectAll()
                
            # set length and angle
            if last and dp and plane:
                self.lengthValue.setText(displayExternal(dp.Length,self.DECIMALS,'Length'))
                a = math.degrees(-DraftVecUtils.angle(dp,plane.u,plane.axis))
                self.angleValue.setText(displayExternal(a,self.DECIMALS,'Angle'))
                
            
    def getDefaultColor(self,type,rgb=False):
        "gets color from the preferences or toolbar"
        if type == "snap":
            color = Draft.getParam("snapcolor",4294967295)
            r = ((color>>24)&0xFF)/255
            g = ((color>>16)&0xFF)/255
            b = ((color>>8)&0xFF)/255
        elif type == "ui":
            r = float(self.color.red()/255.0)
            g = float(self.color.green()/255.0)
            b = float(self.color.blue()/255.0)
        elif type == "face":
            r = float(self.facecolor.red()/255.0)
            g = float(self.facecolor.green()/255.0)
            b = float(self.facecolor.blue()/255.0)
        elif type == "constr":
            color = QtGui.QColor(Draft.getParam("constructioncolor",746455039)>>8)
            r = color.red()/255.0
            g = color.green()/255.0
            b = color.blue()/255.0
        else: 
            print("draft: error: couldn't get a color for ",type," type.")
        if rgb:
            return("rgb("+str(int(r*255))+","+str(int(g*255))+","+str(int(b*255))+")")
        else:
            return (r,g,b)

    def cross(self,on=True):
        "deprecated"
        pass
        
    def toggleConstrMode(self,checked):
        self.baseWidget.setStyleSheet("#constrButton:Checked {background-color: "+self.getDefaultColor("constr",rgb=True)+" }")
        self.constrMode = checked

    def toggleContinue(self):
        self.continueMode = not self.continueMode
        try:
            if hasattr(self,"continueCmd"):
                self.continueCmd.toggle()
            if hasattr(self,"panel"):
                if hasattr(self.panel,"form"):
                    if isinstance(self.panel.form,list):
                        for w in self.panel.form:
                            c = w.findChild(QtGui.QCheckBox,"ContinueCmd")
                            if c:
                                c.toggle()
                    else:
                        c = self.panel.form.findChild(QtGui.QCheckBox,"ContinueCmd")
                        if c:
                            c.toggle()
        except:
            pass

    def isConstructionMode(self):
        if self.tray or (not self.taskmode):
            return self.constrButton.isChecked()
        else:
            return False

    def drawPage(self):
        self.sourceCmd.draw()

    def changePage(self,index):
        pagename = str(self.pageBox.itemText(index))
        vobj = FreeCADGui.ActiveDocument.getObject(pagename)
        if vobj:
            self.scaleBox.setEditText(str(vobj.HintScale))
            self.marginXValue.setValue(float(vobj.HintOffsetX))
            self.marginYValue.setValue(float(vobj.HintOffsetY))

    def selectplane(self):
        FreeCADGui.runCommand("Draft_SelectPlane")

    def popupMenu(self,mlist):
        "pops up a menu filled with the given list"
        self.groupmenu = QtGui.QMenu()
        for i in mlist:
            self.groupmenu.addAction(i)
        pos = FreeCADGui.getMainWindow().cursor().pos()
        self.groupmenu.popup(pos)
        QtCore.QObject.connect(self.groupmenu,QtCore.SIGNAL("triggered(QAction *)"),self.popupTriggered)

    def popupTriggered(self,action):
        self.sourceCmd.proceed(str(action.text()))

    def setAddMode(self,bool):
        if self.addButton.isChecked():
            self.delButton.setChecked(False)
            self.symmetricButton.setChecked(False)
            self.sharpButton.setChecked(False)
            self.tangentButton.setChecked(False)

    def setDelMode(self,bool):
        if self.delButton.isChecked():
            self.addButton.setChecked(False)
            self.symmetricButton.setChecked(False)
            self.sharpButton.setChecked(False)
            self.tangentButton.setChecked(False)

    def setSharpMode(self,bool):
        if self.sharpButton.isChecked():
            self.tangentButton.setChecked(False)
            self.symmetricButton.setChecked(False)
            self.addButton.setChecked(False)
            self.delButton.setChecked(False)

    def setTangentMode(self,bool):
        if self.tangentButton.isChecked():
            self.sharpButton.setChecked(False)
            self.symmetricButton.setChecked(False)
            self.addButton.setChecked(False)
            self.delButton.setChecked(False)

    def setSymmetricMode(self,bool):
        if self.symmetricButton.isChecked():
            self.sharpButton.setChecked(False)
            self.tangentButton.setChecked(False)
            self.addButton.setChecked(False)
            self.delButton.setChecked(False)

    def setRadiusValue(self,val,unit=None):
        #print("DEBUG: setRadiusValue val: ", val, " unit: ", unit)
        if  not isinstance(val, (int, float)):       #??some code passes strings or ??? 
            t = val
        elif unit:
            t= displayExternal(val,self.DECIMALS, unit)
        else:
            print("Error: setRadiusValue called for number without Dimension")
            t = displayExternal(val,self.DECIMALS, None)
        self.radiusValue.setText(t)
        self.radiusValue.setFocus()
        

    def show(self):
        if not self.taskmode:
            self.draftWidget.setVisible(True)

    def hide(self):
        if not self.taskmode:
            self.draftWidget.setVisible(False)

    def getXPM(self,iconname,size=16):
        i = QtGui.QIcon(":/icons/"+iconname+".svg")
        p = i.pixmap(size,size)
        a = QtCore.QByteArray()
        b = QtCore.QBuffer(a)
        b.open(QtCore.QIODevice.WriteOnly)
        p.save(b,"XPM")
        b.close()
        return str(a)

    def togglesnap(self):
        if hasattr(FreeCADGui,"Snapper"):
            FreeCADGui.Snapper.toggle()

    def toggleradius(self,val):
        if hasattr(FreeCADGui,"Snapper"):
            par = Draft.getParam("snapRange",10)
            Draft.setParam("snapRange",par+val)
            FreeCADGui.Snapper.showradius()

    def constrain(self,val):
        if val == "angle":
            self.alock = not(self.alock)
            self.angleLock.setChecked(self.alock)
        elif self.mask == val:
            self.mask = None
            if hasattr(FreeCADGui,"Snapper"):
                FreeCADGui.Snapper.mask = None
        else:
            self.mask = val
            if hasattr(FreeCADGui,"Snapper"):
                FreeCADGui.Snapper.mask = val

    def changeXValue(self,d):
        self.x = d

    def changeYValue(self,d):
        self.y = d

    def changeZValue(self,d):
        self.z = d

    def changeRadiusValue(self,d):
        self.radius = d

    def changeOffsetValue(self,d):
        self.offset = d

    def changeSSizeValue(self,d):
        self.SSize = d

    def changeSTrackValue(self,d):
        self.STrack = d
        
    def changeLengthValue(self,d):
        v = FreeCAD.Vector(self.x,self.y,self.z)
        v = DraftVecUtils.scaleTo(v,d)
        self.xValue.setText(displayExternal(v.x,self.DECIMALS,'Length'))
        self.yValue.setText(displayExternal(v.y,self.DECIMALS,'Length'))
        self.zValue.setText(displayExternal(v.z,self.DECIMALS,'Length'))
        
    def changeAngleValue(self,d):
        v = FreeCAD.Vector(self.x,self.y,self.z)
        a = DraftVecUtils.angle(v,FreeCAD.DraftWorkingPlane.u,FreeCAD.DraftWorkingPlane.axis)
        a = math.radians(d)+a
        v=DraftVecUtils.rotate(v,a,FreeCAD.DraftWorkingPlane.axis)
        self.xValue.setText(displayExternal(v.x,self.DECIMALS,'Length'))
        self.yValue.setText(displayExternal(v.y,self.DECIMALS,'Length'))
        self.zValue.setText(displayExternal(v.z,self.DECIMALS,'Length'))
        
    def toggleAngle(self,bool):
        self.alock = self.angleLock.isChecked()
        FreeCADGui.Snapper.setAngle()
            
            

#---------------------------------------------------------------------------
# TaskView operations
#---------------------------------------------------------------------------
	                
    def setWatchers(self):
        class DraftCreateWatcher:
            def __init__(self):
                self.commands = ["Draft_Line","Draft_Wire",
                                 "Draft_Rectangle","Draft_Arc",
                                 "Draft_Circle","Draft_BSpline",
                                 "Draft_Text","Draft_Dimension",
                                 "Draft_ShapeString","Draft_BezCurve"]
                self.title = "Create objects"
            def shouldShow(self):
                return (FreeCAD.ActiveDocument != None) and (not FreeCADGui.Selection.getSelection())

        class DraftModifyWatcher:
            def __init__(self):
                self.commands = ["Draft_Move","Draft_Rotate",
                                 "Draft_Scale","Draft_Offset",
                                 "Draft_Trimex","Draft_Upgrade",
                                 "Draft_Downgrade","Draft_Edit",
                                 "Draft_Drawing"]
                self.title = "Modify objects"
            def shouldShow(self):
                return (FreeCAD.ActiveDocument != None) and (FreeCADGui.Selection.getSelection() != [])

        # OBSOLETE               
        #class DraftTrayWatcher:
        #    def __init__(self,traywidget):
        #        self.form = traywidget
        #        self.widgets = [self.form]
        #    def shouldShow(self):
        #        return True
        #self.traywidget = QtGui.QWidget()
        #self.tray = QtGui.QVBoxLayout(self.traywidget)
        #self.tray.setObjectName("traylayout")
        #self.toptray = QtGui.QHBoxLayout()
        #self.bottomtray = QtGui.QHBoxLayout()
        #self.tray.addLayout(self.toptray)
        #self.tray.addLayout(self.bottomtray)
        #self.setupTray()
        #self.setupStyle()
        #w = DraftTrayWatcher(self.traywidget)        
        #FreeCADGui.Control.addTaskWatcher([w,DraftCreateWatcher(),DraftModifyWatcher()])
        FreeCADGui.Control.addTaskWatcher([DraftCreateWatcher(),DraftModifyWatcher()])
                                
    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.LanguageChange:
            #print("Language changed!")
            self.ui.retranslateUi(self)

    def Activated(self):
        if self.taskmode:
            self.setWatchers()
            if hasattr(self,"tray"):
                self.tray.show()
        else:
            self.draftWidget.setVisible(True)
            self.draftWidget.toggleViewAction().setVisible(True)

    def Deactivated(self):
        if (FreeCAD.activeDraftCommand != None):
            self.continueMode = False
            FreeCAD.activeDraftCommand.finish()
        if self.taskmode:
            FreeCADGui.Control.clearTaskWatcher()
            #self.tray = None
            if hasattr(self,"tray"):
                self.tray.hide()
        else:
            self.draftWidget.setVisible(False)
            self.draftWidget.toggleViewAction().setVisible(False)
                        
if not hasattr(FreeCADGui,"draftToolBar"):
    FreeCADGui.draftToolBar = DraftToolBar()
#----End of Python Features Definitions----#
   
if not hasattr(FreeCADGui,"Snapper"):
    import DraftSnap
