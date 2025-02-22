/***************************************************************************
 *   Copyright (c) 2008 J�rgen Riegel (juergen.riegel@web.de)              *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public           *
 *   License as published by the Free Software Foundation; either          *
 *   version 2 of the License, or (at your option) any later version.      *
 *                                                                         *
 *   This library  is distributed in the hope that it will be useful,      *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with this library; see the file COPYING.LIB. If not,    *
 *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
 *   Suite 330, Boston, MA  02111-1307, USA                                *
 *                                                                         *
 ***************************************************************************/


#include "PreCompiled.h"
#ifndef _PreComp_
# include <TopoDS_Shape.hxx>
# include <TopoDS_Face.hxx>
# include <TopoDS.hxx>
# include <BRepAdaptor_Surface.hxx>
# include <QApplication>
# include <QInputDialog>
# include <QMessageBox>
#endif

#include <App/DocumentObjectGroup.h>
#include <Gui/Application.h>
#include <Gui/Document.h>
#include <Gui/Command.h>
#include <Gui/Control.h>
#include <Gui/MainWindow.h>
#include <Gui/DlgEditFileIncludeProptertyExternal.h>
#include <Gui/SelectionFilter.h>

#include <Mod/Sketcher/App/SketchObjectSF.h>
#include <Mod/Sketcher/App/SketchObject.h>
#include <Mod/Part/App/Part2DObject.h>

#include "SketchOrientationDialog.h"
#include "SketchMirrorDialog.h"
#include "ViewProviderSketch.h"
#include "TaskSketcherValidation.h"
#include "../App/Constraint.h"

using namespace std;
using namespace SketcherGui;
using namespace Part;

/* Sketch commands =======================================================*/
DEF_STD_CMD_A(CmdSketcherNewSketch);

CmdSketcherNewSketch::CmdSketcherNewSketch()
    :Command("Sketcher_NewSketch")
{
    sAppModule      = "Sketcher";
    sGroup          = QT_TR_NOOP("Sketcher");
    sMenuText       = QT_TR_NOOP("Create sketch");
    sToolTipText    = QT_TR_NOOP("Create a new sketch");
    sWhatsThis      = "Sketcher_NewSketch";
    sStatusTip      = sToolTipText;
    sPixmap         = "Sketcher_NewSketch";
}

void CmdSketcherNewSketch::activated(int iMsg)
{
    Gui::SelectionFilter FaceFilter  ("SELECT Part::Feature SUBELEMENT Face COUNT 1");

    if (FaceFilter.match()) {
        // get the selected object
        Part::Feature *part = static_cast<Part::Feature*>(FaceFilter.Result[0][0].getObject());
        Base::Placement ObjectPos = part->Placement.getValue();
        const std::vector<std::string> &sub = FaceFilter.Result[0][0].getSubNames();
        if (sub.empty()) {
            // No assert for wrong user input!
            QMessageBox::warning(Gui::getMainWindow(),
                qApp->translate(className(),"No sub-elements selected"),
                qApp->translate(className(),"You have to select a single face as support for a sketch!"));
            return;
        }
        else if (sub.size() > 1) {
            // No assert for wrong user input!
            QMessageBox::warning(Gui::getMainWindow(), QObject::tr("Several sub-elements selected"),
                QObject::tr("You have to select a single face as support for a sketch!"));
            return;
        }
        // get the selected sub shape (a Face)
        const Part::TopoShape &shape = part->Shape.getValue();
        TopoDS_Shape sh = shape.getSubShape(sub[0].c_str());
        const TopoDS_Face& face = TopoDS::Face(sh);
        if (face.IsNull()){
            // No assert for wrong user input!
            QMessageBox::warning(Gui::getMainWindow(), QObject::tr("No support face selected"),
                QObject::tr("You have to select a face as support for a sketch!"));
            return;
        }

        BRepAdaptor_Surface adapt(face);
        if (adapt.GetType() != GeomAbs_Plane){
            QMessageBox::warning(Gui::getMainWindow(), QObject::tr("No planar support"),
                QObject::tr("You need a planar face as support for a sketch!"));
            return;
        }

        std::string supportString = FaceFilter.Result[0][0].getAsPropertyLinkSubString();

        // create Sketch on Face
        std::string FeatName = getUniqueObjectName("Sketch");

        openCommand("Create a Sketch on Face");
        doCommand(Doc,"App.activeDocument().addObject('Sketcher::SketchObject','%s')",FeatName.c_str());
        doCommand(Gui,"App.activeDocument().%s.Support = %s",FeatName.c_str(),supportString.c_str());
        doCommand(Gui,"App.activeDocument().recompute()");  // recompute the sketch placement based on its support
        //doCommand(Gui,"Gui.activeDocument().activeView().setCamera('%s')",cam.c_str());
        doCommand(Gui,"Gui.activeDocument().setEdit('%s')",FeatName.c_str());
        App::DocumentObjectGroup* grp = part->getGroup();
        if (grp) {
            doCommand(Doc,"App.activeDocument().%s.addObject(App.activeDocument().%s)"
                         ,grp->getNameInDocument(),FeatName.c_str());
        }
    }
    else {
        // ask user for orientation
        SketchOrientationDialog Dlg;

        if (Dlg.exec() != QDialog::Accepted)
            return; // canceled
        Base::Vector3d p = Dlg.Pos.getPosition();
        Base::Rotation r = Dlg.Pos.getRotation();

        // do the right view direction
        std::string camstring;
        switch(Dlg.DirType){
            case 0:
                camstring = "#Inventor V2.1 ascii \\n OrthographicCamera {\\n viewportMapping ADJUST_CAMERA \\n position 0 0 87 \\n orientation 0 0 1  0 \\n nearDistance -112.88701 \\n farDistance 287.28702 \\n aspectRatio 1 \\n focalDistance 87 \\n height 143.52005 }";
                break;
            case 1:
                camstring = "#Inventor V2.1 ascii \\n OrthographicCamera {\\n viewportMapping ADJUST_CAMERA \\n position 0 0 -87 \\n orientation -1 0 0  3.1415927 \\n nearDistance -112.88701 \\n farDistance 287.28702 \\n aspectRatio 1 \\n focalDistance 87 \\n height 143.52005 }";
                break;
            case 2:
                camstring = "#Inventor V2.1 ascii \\n OrthographicCamera {\\n viewportMapping ADJUST_CAMERA\\n  position 0 -87 0 \\n  orientation -1 0 0  4.712389\\n  nearDistance -112.88701\\n  farDistance 287.28702\\n  aspectRatio 1\\n  focalDistance 87\\n  height 143.52005\\n\\n}";
                break;
            case 3:
                camstring = "#Inventor V2.1 ascii \\n OrthographicCamera {\\n viewportMapping ADJUST_CAMERA\\n  position 0 87 0 \\n  orientation 0 0.70710683 0.70710683  3.1415927\\n  nearDistance -112.88701\\n  farDistance 287.28702\\n  aspectRatio 1\\n  focalDistance 87\\n  height 143.52005\\n\\n}";
                break;
            case 4:
                camstring = "#Inventor V2.1 ascii \\n OrthographicCamera {\\n viewportMapping ADJUST_CAMERA\\n  position 87 0 0 \\n  orientation 0.57735026 0.57735026 0.57735026  2.0943952 \\n  nearDistance -112.887\\n  farDistance 287.28699\\n  aspectRatio 1\\n  focalDistance 87\\n  height 143.52005\\n\\n}";
                break;
            case 5:
                camstring = "#Inventor V2.1 ascii \\n OrthographicCamera {\\n viewportMapping ADJUST_CAMERA\\n  position -87 0 0 \\n  orientation -0.57735026 0.57735026 0.57735026  4.1887903 \\n  nearDistance -112.887\\n  farDistance 287.28699\\n  aspectRatio 1\\n  focalDistance 87\\n  height 143.52005\\n\\n}";
                break;
        }
        std::string FeatName = getUniqueObjectName("Sketch");

        openCommand("Create a new Sketch");
        doCommand(Doc,"App.activeDocument().addObject('Sketcher::SketchObject','%s')",FeatName.c_str());
        doCommand(Doc,"App.activeDocument().%s.Placement = App.Placement(App.Vector(%f,%f,%f),App.Rotation(%f,%f,%f,%f))",FeatName.c_str(),p.x,p.y,p.z,r[0],r[1],r[2],r[3]);
        doCommand(Gui,"Gui.activeDocument().activeView().setCamera('%s')",camstring.c_str());
        doCommand(Gui,"Gui.activeDocument().setEdit('%s')",FeatName.c_str());
    }

}

bool CmdSketcherNewSketch::isActive(void)
{
    if (getActiveGuiDocument())
        return true;
    else
        return false;
}

DEF_STD_CMD_A(CmdSketcherEditSketch);

CmdSketcherEditSketch::CmdSketcherEditSketch()
    :Command("Sketcher_EditSketch")
{
    sAppModule      = "Sketcher";
    sGroup          = QT_TR_NOOP("Sketcher");
    sMenuText       = QT_TR_NOOP("Edit sketch");
    sToolTipText    = QT_TR_NOOP("Edit the selected sketch");
    sWhatsThis      = "Sketcher_EditSketch";
    sStatusTip      = sToolTipText;
    sPixmap         = "Sketcher_EditSketch";
}

void CmdSketcherEditSketch::activated(int iMsg)
{
    Gui::SelectionFilter SketchFilter("SELECT Sketcher::SketchObject COUNT 1");

    if (SketchFilter.match()) {
        Sketcher::SketchObject *Sketch = static_cast<Sketcher::SketchObject*>(SketchFilter.Result[0][0].getObject());
        openCommand("Edit Sketch");
        doCommand(Gui,"Gui.activeDocument().setEdit('%s')",Sketch->getNameInDocument());
    }
}

bool CmdSketcherEditSketch::isActive(void)
{
    return Gui::Selection().countObjectsOfType(Sketcher::SketchObject::getClassTypeId()) == 1;
}

DEF_STD_CMD_A(CmdSketcherLeaveSketch);

CmdSketcherLeaveSketch::CmdSketcherLeaveSketch()
  : Command("Sketcher_LeaveSketch")
{
    sAppModule      = "Sketcher";
    sGroup          = QT_TR_NOOP("Sketcher");
    sMenuText       = QT_TR_NOOP("Leave sketch");
    sToolTipText    = QT_TR_NOOP("Close the editing of the sketch");
    sWhatsThis      = "Sketcher_LeaveSketch";
    sStatusTip      = sToolTipText;
    sPixmap         = "Sketcher_LeaveSketch";
    eType           = 0;
}

void CmdSketcherLeaveSketch::activated(int iMsg)
{
    Gui::Document *doc = getActiveGuiDocument();
    
    if (doc) {
        // checks if a Sketch Viewprovider is in Edit and is in no special mode
        SketcherGui::ViewProviderSketch* vp = dynamic_cast<SketcherGui::ViewProviderSketch*>(doc->getInEdit());
        if (vp && vp->getSketchMode() != ViewProviderSketch::STATUS_NONE)
            vp->purgeHandler();
    }
    
    openCommand("Sketch changed");
    doCommand(Gui,"Gui.activeDocument().resetEdit()");
    doCommand(Doc,"App.ActiveDocument.recompute()");
    commitCommand();

}

bool CmdSketcherLeaveSketch::isActive(void)
{
    Gui::Document *doc = getActiveGuiDocument();
    if (doc) {
        // checks if a Sketch Viewprovider is in Edit and is in no special mode
        SketcherGui::ViewProviderSketch* vp = dynamic_cast<SketcherGui::ViewProviderSketch*>(doc->getInEdit());
        if (vp /*&& vp->getSketchMode() == ViewProviderSketch::STATUS_NONE*/)
            return true;
    }
    return false;
}

DEF_STD_CMD_A(CmdSketcherReorientSketch);

CmdSketcherReorientSketch::CmdSketcherReorientSketch()
    :Command("Sketcher_ReorientSketch")
{
    sAppModule      = "Sketcher";
    sGroup          = QT_TR_NOOP("Sketcher");
    sMenuText       = QT_TR_NOOP("Reorient sketch...");
    sToolTipText    = QT_TR_NOOP("Reorient the selected sketch");
    sWhatsThis      = "Sketcher_ReorientSketch";
    sStatusTip      = sToolTipText;
}

void CmdSketcherReorientSketch::activated(int iMsg)
{
    Sketcher::SketchObject* sketch = Gui::Selection().getObjectsOfType<Sketcher::SketchObject>().front();
    if (sketch->Support.getValue()) {
        int ret = QMessageBox::question(Gui::getMainWindow(),
            qApp->translate("Sketcher_ReorientSketch","Sketch has support"),
            qApp->translate("Sketcher_ReorientSketch","Sketch with a support face cannot be reoriented.\n"
                                                      "Do you want to detach it from the support?"),
            QMessageBox::Yes|QMessageBox::No);
        if (ret == QMessageBox::No)
            return;
        sketch->Support.setValue(0);
    }

    // ask user for orientation
    SketchOrientationDialog Dlg;

    if (Dlg.exec() != QDialog::Accepted)
        return; // canceled
    Base::Vector3d p = Dlg.Pos.getPosition();
    Base::Rotation r = Dlg.Pos.getRotation();

    // do the right view direction
    std::string camstring;
    switch(Dlg.DirType){
        case 0:
            camstring = "#Inventor V2.1 ascii \\n OrthographicCamera {\\n viewportMapping ADJUST_CAMERA \\n "
                "position 0 0 87 \\n orientation 0 0 1  0 \\n nearDistance -112.88701 \\n farDistance 287.28702 \\n "
                "aspectRatio 1 \\n focalDistance 87 \\n height 143.52005 }";
            break;
        case 1:
            camstring = "#Inventor V2.1 ascii \\n OrthographicCamera {\\n viewportMapping ADJUST_CAMERA \\n "
                "position 0 0 -87 \\n orientation -1 0 0  3.1415927 \\n nearDistance -112.88701 \\n farDistance 287.28702 \\n "
                "aspectRatio 1 \\n focalDistance 87 \\n height 143.52005 }";
            break;
        case 2:
            camstring = "#Inventor V2.1 ascii \\n OrthographicCamera {\\n viewportMapping ADJUST_CAMERA\\n "
                "position 0 -87 0 \\n  orientation -1 0 0  4.712389\\n  nearDistance -112.88701\\n  farDistance 287.28702\\n "
                "aspectRatio 1\\n  focalDistance 87\\n  height 143.52005\\n\\n}";
            break;
        case 3:
            camstring = "#Inventor V2.1 ascii \\n OrthographicCamera {\\n viewportMapping ADJUST_CAMERA\\n "
                "position 0 87 0 \\n  orientation 0 0.70710683 0.70710683  3.1415927\\n  nearDistance -112.88701\\n  farDistance 287.28702\\n "
                "aspectRatio 1\\n  focalDistance 87\\n  height 143.52005\\n\\n}";
            break;
        case 4:
            camstring = "#Inventor V2.1 ascii \\n OrthographicCamera {\\n viewportMapping ADJUST_CAMERA\\n "
                "position 87 0 0 \\n  orientation 0.57735026 0.57735026 0.57735026  2.0943952 \\n  nearDistance -112.887\\n  farDistance 287.28699\\n "
                "aspectRatio 1\\n  focalDistance 87\\n  height 143.52005\\n\\n}";
            break;
        case 5:
            camstring = "#Inventor V2.1 ascii \\n OrthographicCamera {\\n viewportMapping ADJUST_CAMERA\\n "
                "position -87 0 0 \\n  orientation -0.57735026 0.57735026 0.57735026  4.1887903 \\n  nearDistance -112.887\\n  farDistance 287.28699\\n "
                "aspectRatio 1\\n  focalDistance 87\\n  height 143.52005\\n\\n}";
            break;
    }

    openCommand("Reorient Sketch");
    doCommand(Doc,"App.ActiveDocument.%s.Placement = App.Placement(App.Vector(%f,%f,%f),App.Rotation(%f,%f,%f,%f))"
                 ,sketch->getNameInDocument(),p.x,p.y,p.z,r[0],r[1],r[2],r[3]);
    doCommand(Gui,"Gui.ActiveDocument.setEdit('%s')",sketch->getNameInDocument());
}

bool CmdSketcherReorientSketch::isActive(void)
{
    return Gui::Selection().countObjectsOfType
        (Sketcher::SketchObject::getClassTypeId()) == 1;
}

DEF_STD_CMD_A(CmdSketcherMapSketch);

CmdSketcherMapSketch::CmdSketcherMapSketch()
  : Command("Sketcher_MapSketch")
{
    sAppModule      = "Sketcher";
    sGroup          = QT_TR_NOOP("Sketcher");
    sMenuText       = QT_TR_NOOP("Map sketch to face...");
    sToolTipText    = QT_TR_NOOP("Map a sketch to a face");
    sWhatsThis      = "Sketcher_MapSketch";
    sStatusTip      = sToolTipText;
    sPixmap         = "Sketcher_MapSketch";
}

void CmdSketcherMapSketch::activated(int iMsg)
{
    App::Document* doc = App::GetApplication().getActiveDocument();
    std::vector<App::DocumentObject*> sel = doc->getObjectsOfType(Sketcher::SketchObject::getClassTypeId());
    if (sel.empty()) {
        QMessageBox::warning(Gui::getMainWindow(),
            qApp->translate(className(), "No sketch found"),
            qApp->translate(className(), "The document doesn't have a sketch"));
        return;
    }

    bool ok;
    QStringList items;
    for (std::vector<App::DocumentObject*>::iterator it = sel.begin(); it != sel.end(); ++it)
        items.push_back(QString::fromUtf8((*it)->Label.getValue()));
    QString text = QInputDialog::getItem(Gui::getMainWindow(),
        qApp->translate(className(), "Select sketch"),
        qApp->translate(className(), "Select a sketch from the list"),
        items, 0, false, &ok);
    if (!ok) return;
    int index = items.indexOf(text);

    std::string featName = sel[index]->getNameInDocument();
    Gui::SelectionFilter FaceFilter  ("SELECT Part::Feature SUBELEMENT Face COUNT 1");
    if (FaceFilter.match()) {
        // get the selected object
        Part::Feature *part = static_cast<Part::Feature*>(FaceFilter.Result[0][0].getObject());
        Base::Placement ObjectPos = part->Placement.getValue();
        const std::vector<std::string> &sub = FaceFilter.Result[0][0].getSubNames();
        if (sub.empty()) {
            // No assert for wrong user input!
            QMessageBox::warning(Gui::getMainWindow(),
                qApp->translate(className(),"No sub-elements selected"),
                qApp->translate(className(),"You have to select a single face as support for a sketch!"));
            return;
        }
        else if (sub.size() > 1) {
            // No assert for wrong user input!
            QMessageBox::warning(Gui::getMainWindow(),
                qApp->translate(className(),"Several sub-elements selected"),
                qApp->translate(className(),"You have to select a single face as support for a sketch!"));
            return;
        }

        std::vector<App::DocumentObject*> input = part->getOutList();
        if (std::find(input.begin(), input.end(), sel[index]) != input.end()) {
            QMessageBox::warning(Gui::getMainWindow(),
                qApp->translate(className(),"Cyclic dependency"),
                qApp->translate(className(),"You cannot choose a support object depending on the selected sketch!"));
            return;
        }

        // get the selected sub shape (a Face)
        const Part::TopoShape &shape = part->Shape.getValue();
        TopoDS_Shape sh = shape.getSubShape(sub[0].c_str());
        const TopoDS_Face& face = TopoDS::Face(sh);
        if (face.IsNull()) {
            // No assert for wrong user input!
            QMessageBox::warning(Gui::getMainWindow(),
                qApp->translate(className(),"No support face selected"),
                qApp->translate(className(),"You have to select a face as support for a sketch!"));
            return;
        }

        BRepAdaptor_Surface adapt(face);
        if (adapt.GetType() != GeomAbs_Plane){
            QMessageBox::warning(Gui::getMainWindow(),
                qApp->translate(className(),"No planar support"),
                qApp->translate(className(),"You need a planar face as support for a sketch!"));
            return;
        }

        std::string supportString = FaceFilter.Result[0][0].getAsPropertyLinkSubString();

        openCommand("Map a Sketch on Face");
        doCommand(Gui,"App.activeDocument().%s.Support = %s",featName.c_str(),supportString.c_str());
        doCommand(Gui,"App.activeDocument().recompute()");
        doCommand(Gui,"Gui.activeDocument().setEdit('%s')",featName.c_str());
    }
    else {
        QMessageBox::warning(Gui::getMainWindow(),
            qApp->translate(className(), "No face selected"),
            qApp->translate(className(), "No face was selected to map the sketch to"));
    }
}

bool CmdSketcherMapSketch::isActive(void)
{
    return getActiveGuiDocument() != 0;
}

DEF_STD_CMD_A(CmdSketcherViewSketch);

CmdSketcherViewSketch::CmdSketcherViewSketch()
  : Command("Sketcher_ViewSketch")
{
    sAppModule      = "Sketcher";
    sGroup          = QT_TR_NOOP("Sketcher");
    sMenuText       = QT_TR_NOOP("View sketch");
    sToolTipText    = QT_TR_NOOP("View sketch perpendicular to sketch plane");
    sWhatsThis      = "Sketcher_ViewSketch";
    sStatusTip      = sToolTipText;
    sPixmap         = "Sketcher_ViewSketch";
    eType           = 0;
}

void CmdSketcherViewSketch::activated(int iMsg)
{
    Gui::Document *doc = getActiveGuiDocument();
    SketcherGui::ViewProviderSketch* vp = dynamic_cast<SketcherGui::ViewProviderSketch*>(doc->getInEdit());
    doCommand(Gui,"Gui.ActiveDocument.ActiveView.setCameraOrientation(App.ActiveDocument.%s.Placement.Rotation.Q)"
                 ,vp->getObject()->getNameInDocument());
}

bool CmdSketcherViewSketch::isActive(void)
{
    Gui::Document *doc = getActiveGuiDocument();
    if (doc) {
        // checks if a Sketch Viewprovider is in Edit and is in no special mode
        SketcherGui::ViewProviderSketch* vp = dynamic_cast<SketcherGui::ViewProviderSketch*>(doc->getInEdit());
        if (vp /*&& vp->getSketchMode() == ViewProviderSketch::STATUS_NONE*/)
            return true;
    }
    return false;
}

DEF_STD_CMD_A(CmdSketcherValidateSketch);

CmdSketcherValidateSketch::CmdSketcherValidateSketch()
  : Command("Sketcher_ValidateSketch")
{
    sAppModule      = "Sketcher";
    sGroup          = QT_TR_NOOP("Sketcher");
    sMenuText       = QT_TR_NOOP("Validate sketch...");
    sToolTipText    = QT_TR_NOOP("Validate sketch");
    sWhatsThis      = "Sketcher_ValidateSketch";
    sStatusTip      = sToolTipText;
    eType           = 0;
}

void CmdSketcherValidateSketch::activated(int iMsg)
{
    std::vector<Gui::SelectionObject> selection = getSelection().getSelectionEx(0, Sketcher::SketchObject::getClassTypeId());
    if (selection.size() != 1) {
        QMessageBox::warning(Gui::getMainWindow(),
            qApp->translate("CmdSketcherValidateSketch", "Wrong selection"),
            qApp->translate("CmdSketcherValidateSketch", "Select one sketch, please."));
        return;
    }

    Sketcher::SketchObject* Obj = static_cast<Sketcher::SketchObject*>(selection[0].getObject());
    Gui::Control().showDialog(new TaskSketcherValidation(Obj));
}

bool CmdSketcherValidateSketch::isActive(void)
{
    return (hasActiveDocument() && !Gui::Control().activeDialog());
}

DEF_STD_CMD_A(CmdSketcherMirrorSketch);

CmdSketcherMirrorSketch::CmdSketcherMirrorSketch()
: Command("Sketcher_MirrorSketch")
{
    sAppModule      = "Sketcher";
    sGroup          = QT_TR_NOOP("Sketcher");
    sMenuText       = QT_TR_NOOP("Mirror sketch");
    sToolTipText    = QT_TR_NOOP("Mirror sketch");
    sWhatsThis      = "Sketcher_MirrorSketch";
    sStatusTip      = sToolTipText;
    eType           = 0;
    sPixmap         = "Sketcher_MirrorSketch";
}

void CmdSketcherMirrorSketch::activated(int iMsg)
{
    std::vector<Gui::SelectionObject> selection = getSelection().getSelectionEx(0, Sketcher::SketchObject::getClassTypeId());
    if (selection.size() < 1) {
        QMessageBox::warning(Gui::getMainWindow(),
            qApp->translate("CmdSketcherMirrorSketch", "Wrong selection"),
            qApp->translate("CmdSketcherMirrorSketch", "Select one or more sketches, please."));
        return;
    }
    
    // Ask the user which kind of mirroring he wants
    SketchMirrorDialog * smd = new SketchMirrorDialog();
    
    int refgeoid=-1;
    Sketcher::PointPos refposid=Sketcher::none;
    
    if( smd->exec() == QDialog::Accepted ){
        refgeoid=smd->RefGeoid;
        refposid=smd->RefPosid;
        
        delete smd;
    }
    else {
        delete smd;
        return;
    }
    
    App::Document* doc = App::GetApplication().getActiveDocument();
    
    openCommand("Create a mirror Sketch for each sketch");
    
    for (std::vector<Gui::SelectionObject>::const_iterator it=selection.begin(); it != selection.end(); ++it) {
        // create Sketch 
        std::string FeatName = getUniqueObjectName("MirroredSketch");
        
        doCommand(Doc,"App.activeDocument().addObject('Sketcher::SketchObject','%s')",FeatName.c_str());
        
        Sketcher::SketchObject* mirrorsketch = static_cast<Sketcher::SketchObject*>(doc->getObject(FeatName.c_str()));       
        
        const Sketcher::SketchObject* Obj = static_cast<const Sketcher::SketchObject*>((*it).getObject());
        
        Base::Placement pl = Obj->Placement.getValue();
        
        Base::Vector3d p = pl.getPosition();
        Base::Rotation r = pl.getRotation();
        
        doCommand(Doc,"App.activeDocument().%s.Placement = App.Placement(App.Vector(%f,%f,%f),App.Rotation(%f,%f,%f,%f))",
                  FeatName.c_str(),
                  p.x,p.y,p.z,r[0],r[1],r[2],r[3]);
        
        Sketcher::SketchObject* tempsketch = new Sketcher::SketchObject();
        
        int addedGeometries=tempsketch->addGeometry(Obj->getInternalGeometry());
        
        int addedConstraints=tempsketch->addConstraints(Obj->Constraints.getValues());

        std::vector<int> geoIdList;
        
        for(int i=0;i<=addedGeometries;i++)
            geoIdList.push_back(i);
        
        tempsketch->addSymmetric(geoIdList, refgeoid, refposid);
                
        std::vector<Part::Geometry *> tempgeo = tempsketch->getInternalGeometry();
        std::vector<Sketcher::Constraint *> tempconstr = tempsketch->Constraints.getValues();

        std::vector<Part::Geometry *> mirrorgeo (tempgeo.begin()+addedGeometries+1,tempgeo.end());
        std::vector<Sketcher::Constraint *> mirrorconstr (tempconstr.begin()+addedConstraints+1,tempconstr.end());
        
        for(std::vector<Sketcher::Constraint *>::const_iterator itc=mirrorconstr.begin(); itc != mirrorconstr.end(); ++itc) {
 
            if((*itc)->First!=Sketcher::Constraint::GeoUndef || (*itc)->First==-1 || (*itc)->First==-2) // not x, y axes or origin
                (*itc)->First-=(addedGeometries+1);
            if((*itc)->Second!=Sketcher::Constraint::GeoUndef || (*itc)->Second==-1 || (*itc)->Second==-2) // not x, y axes or origin
                (*itc)->Second-=(addedGeometries+1);
            if((*itc)->Third!=Sketcher::Constraint::GeoUndef || (*itc)->Third==-1 || (*itc)->Third==-2) // not x, y axes or origin
                (*itc)->Third-=(addedGeometries+1);
        }
        
        mirrorsketch->addGeometry(mirrorgeo);
        mirrorsketch->addConstraints(mirrorconstr);
        
        delete tempsketch;
    }
    
    doCommand(Gui,"App.activeDocument().recompute()");
    
}

bool CmdSketcherMirrorSketch::isActive(void)
{
    return (hasActiveDocument() && !Gui::Control().activeDialog());
}

DEF_STD_CMD_A(CmdSketcherMergeSketches);

CmdSketcherMergeSketches::CmdSketcherMergeSketches()
: Command("Sketcher_MergeSketches")
{
    sAppModule      = "Sketcher";
    sGroup          = QT_TR_NOOP("Sketcher");
    sMenuText       = QT_TR_NOOP("Merge sketches");
    sToolTipText    = QT_TR_NOOP("Merge sketches");
    sWhatsThis      = "Sketcher_MergeSketches";
    sStatusTip      = sToolTipText;
    eType           = 0;
    sPixmap         = "Sketcher_MergeSketch";
}

void CmdSketcherMergeSketches::activated(int iMsg)
{
    std::vector<Gui::SelectionObject> selection = getSelection().getSelectionEx(0, Sketcher::SketchObject::getClassTypeId());
    if (selection.size() < 2) {
        QMessageBox::warning(Gui::getMainWindow(),
                             qApp->translate("CmdSketcherMergeSketches", "Wrong selection"),
                             qApp->translate("CmdSketcherMergeSketches", "Select at least two sketches, please."));
        return;
    }

    App::Document* doc = App::GetApplication().getActiveDocument();

    // create Sketch 
    std::string FeatName = getUniqueObjectName("Sketch");

    openCommand("Create a merge Sketch");
    doCommand(Doc,"App.activeDocument().addObject('Sketcher::SketchObject','%s')",FeatName.c_str());

    Sketcher::SketchObject* mergesketch = static_cast<Sketcher::SketchObject*>(doc->getObject(FeatName.c_str()));

    int baseGeometry=0;
    int baseConstraints=0;

    for (std::vector<Gui::SelectionObject>::const_iterator it=selection.begin(); it != selection.end(); ++it) {
        const Sketcher::SketchObject* Obj = static_cast<const Sketcher::SketchObject*>((*it).getObject());
        int addedGeometries=mergesketch->addGeometry(Obj->getInternalGeometry());

        int addedConstraints=mergesketch->addConstraints(Obj->Constraints.getValues());

        for(int i=0; i<=(addedConstraints-baseConstraints); i++){
            Sketcher::Constraint * constraint= mergesketch->Constraints.getValues()[i+baseConstraints];

            if(constraint->First!=Sketcher::Constraint::GeoUndef || constraint->First==-1 || constraint->First==-2) // not x, y axes or origin
                constraint->First+=baseGeometry;
            if(constraint->Second!=Sketcher::Constraint::GeoUndef || constraint->Second==-1 || constraint->Second==-2) // not x, y axes or origin
                constraint->Second+=baseGeometry;
            if(constraint->Third!=Sketcher::Constraint::GeoUndef || constraint->Third==-1 || constraint->Third==-2) // not x, y axes or origin
                constraint->Third+=baseGeometry;
        }

        baseGeometry=addedGeometries+1;
        baseConstraints=addedConstraints+1;
    }

    doCommand(Gui,"App.activeDocument().recompute()");
}

bool CmdSketcherMergeSketches::isActive(void)
{
    return (hasActiveDocument() && !Gui::Control().activeDialog());
}

void CreateSketcherCommands(void)
{
    Gui::CommandManager &rcCmdMgr = Gui::Application::Instance->commandManager();

    rcCmdMgr.addCommand(new CmdSketcherNewSketch());
    rcCmdMgr.addCommand(new CmdSketcherEditSketch());
    rcCmdMgr.addCommand(new CmdSketcherLeaveSketch());
    rcCmdMgr.addCommand(new CmdSketcherReorientSketch());
    rcCmdMgr.addCommand(new CmdSketcherMapSketch());
    rcCmdMgr.addCommand(new CmdSketcherViewSketch());
    rcCmdMgr.addCommand(new CmdSketcherValidateSketch());
    rcCmdMgr.addCommand(new CmdSketcherMirrorSketch());
    rcCmdMgr.addCommand(new CmdSketcherMergeSketches());
}
