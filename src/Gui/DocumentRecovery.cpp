/***************************************************************************
 *   Copyright (c) 2015 Werner Mayer <wmayer[at]users.sourceforge.net>     *
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


// Implement FileWriter which puts files into a directory
// write a property to file only when it has been modified
// implement xml meta file

#include "PreCompiled.h"

#ifndef _PreComp_
# include <QApplication>
# include <QCloseEvent>
# include <QDateTime>
# include <QDebug>
# include <QDir>
# include <QFile>
# include <QHeaderView>
# include <QPushButton>
# include <QTextStream>
# include <QTreeWidgetItem>
# include <QMap>
# include <QList>
# include <QVector>
#endif

#include "DocumentRecovery.h"
#include "ui_DocumentRecovery.h"
#include "WaitCursor.h"

#include <Base/Exception.h>

#include <App/Application.h>
#include <App/Document.h>

#include <Gui/Application.h>
#include <Gui/Document.h>

#include <QDomDocument>

using namespace Gui;
using namespace Gui::Dialog;


namespace Gui { namespace Dialog {
class DocumentRecoveryPrivate
{
public:
    typedef QMap<QString, QString> XmlConfig;

    enum Status {
        Unknown = 0, /*!< The file is not available */
        Created = 1, /*!< The file was created but not processed so far*/
        Overage = 2, /*!< The recovery file is older than the actual project file */
        Success = 3, /*!< The file could be recovered */
        Failure = 4, /*!< The file could not be recovered */
    };
    struct Info {
        QString projectFile;
        QString xmlFile;
        QString label;
        QString fileName;
        QString tooltip;
        Status status;
    };
    Ui_DocumentRecovery ui;
    bool recovered;
    QList<Info> recoveryInfo;

    Info getRecoveryInfo(const QFileInfo&) const;
    void writeRecoveryInfo(const Info&) const;
    XmlConfig readXmlFile(const QString& fn) const;
};

}
}

DocumentRecovery::DocumentRecovery(const QList<QFileInfo>& dirs, QWidget* parent)
  : QDialog(parent), d_ptr(new DocumentRecoveryPrivate())
{
    d_ptr->ui.setupUi(this);
    d_ptr->ui.buttonBox->button(QDialogButtonBox::Ok)->setText(tr("Start Recovery"));
    d_ptr->ui.treeWidget->header()->setResizeMode(QHeaderView::Stretch);

    d_ptr->recovered = false;

    for (QList<QFileInfo>::const_iterator it = dirs.begin(); it != dirs.end(); ++it) {
        DocumentRecoveryPrivate::Info info = d_ptr->getRecoveryInfo(*it);

        if (info.status == DocumentRecoveryPrivate::Created) {
            d_ptr->recoveryInfo << info;

            QTreeWidgetItem* item = new QTreeWidgetItem(d_ptr->ui.treeWidget);
            item->setText(0, info.label);
            item->setToolTip(0, info.tooltip);
            item->setText(1, tr("Not yet recovered"));
            d_ptr->ui.treeWidget->addTopLevelItem(item);
        }
    }
}

DocumentRecovery::~DocumentRecovery()
{
}

bool DocumentRecovery::foundDocuments() const
{
    Q_D(const DocumentRecovery);
    return (!d->recoveryInfo.isEmpty());
}

void DocumentRecovery::closeEvent(QCloseEvent* e)
{
    Q_D(DocumentRecovery);

    if (!d->recoveryInfo.isEmpty())
        e->ignore();
}

void DocumentRecovery::accept()
{
    Q_D(DocumentRecovery);

    if (!d->recovered) {

        WaitCursor wc;
        int index = 0;
        for (QList<DocumentRecoveryPrivate::Info>::iterator it = d->recoveryInfo.begin(); it != d->recoveryInfo.end(); ++it, index++) {
            std::string documentName;
            QString errorInfo;
            QTreeWidgetItem* item = d_ptr->ui.treeWidget->topLevelItem(index);

            try {
                QString file = it->projectFile;
                App::Document* document = App::GetApplication().newDocument();
                documentName = document->getName();
                document->FileName.setValue(file.toUtf8().constData());

                // If something goes wrong an exception will be thrown here
                document->restore();

                file = it->fileName;
                document->FileName.setValue(file.toUtf8().constData());
                document->Label.setValue(it->label.toUtf8().constData());

                // Set the modified flag so that the user cannot close by accident
                Gui::Document* guidoc = Gui::Application::Instance->getDocument(document);
                if (guidoc) {
                    guidoc->setModified(true);
                }
            }
            catch (const std::exception& e) {
                errorInfo = QString::fromLatin1(e.what());
            }
            catch (const Base::Exception& e) {
                errorInfo = QString::fromLatin1(e.what());
            }
            catch (...) {
                errorInfo = tr("Unknown problem occurred");
            }

            // an error occurred so close the document again
            if (!errorInfo.isEmpty()) {
                if (!documentName.empty())
                    App::GetApplication().closeDocument(documentName.c_str());

                it->status = DocumentRecoveryPrivate::Failure;

                if (item) {
                    item->setText(1, tr("Failed to recover"));
                    item->setToolTip(1, errorInfo);
                    item->setForeground(1, QColor(170,0,0));
                }
            }
            // everything OK
            else {
                it->status = DocumentRecoveryPrivate::Success;

                if (item) {
                    item->setText(1, tr("Successfully recovered"));
                    item->setForeground(1, QColor(0,170,0));
                }
            }

            // write back current status
            d->writeRecoveryInfo(*it);
        }

        d->ui.buttonBox->button(QDialogButtonBox::Ok)->setText(tr("Finish"));
        d->ui.buttonBox->button(QDialogButtonBox::Cancel)->setEnabled(false);
        d->recovered = true;
    }
    else {
        QDialog::accept();
    }
}

void DocumentRecoveryPrivate::writeRecoveryInfo(const DocumentRecoveryPrivate::Info& info) const
{
    // Write recovery meta file
    QFile file(info.xmlFile);
    if (file.open(QFile::WriteOnly)) {
        QTextStream str(&file);
        str.setCodec("UTF-8");
        str << "<?xml version='1.0' encoding='utf-8'?>" << endl
            << "<AutoRecovery SchemaVersion=\"1\">" << endl;
        switch (info.status) {
        case Created:
            str << "  <Status>Created</Status>" << endl;
            break;
        case Overage:
            str << "  <Status>Deprecated</Status>" << endl;
            break;
        case Success:
            str << "  <Status>Success</Status>" << endl;
            break;
        case Failure:
            str << "  <Status>Failure</Status>" << endl;
            break;
        default:
            str << "  <Status>Unknown</Status>" << endl;
            break;
        }
        str << "  <Label>" << info.label << "</Label>" << endl;
        str << "  <FileName>" << info.fileName << "</FileName>" << endl;
        str << "</AutoRecovery>" << endl;
        file.close();
    }
}

DocumentRecoveryPrivate::Info DocumentRecoveryPrivate::getRecoveryInfo(const QFileInfo& fi) const
{
    DocumentRecoveryPrivate::Info info;
    info.status = DocumentRecoveryPrivate::Unknown;
    info.label = qApp->translate("StdCmdNew","Unnamed");

    QDir doc_dir(fi.absoluteFilePath());
    if (doc_dir.exists(QLatin1String("fc_recovery_file.fcstd"))) {
        info.status = DocumentRecoveryPrivate::Created;
        QString file = doc_dir.absoluteFilePath(QLatin1String("fc_recovery_file.fcstd"));
        info.projectFile = file;
        info.tooltip = fi.fileName();

        // when the Xml meta exists get some relevant information
        info.xmlFile = doc_dir.absoluteFilePath(QLatin1String("fc_recovery_file.xml"));
        if (doc_dir.exists(QLatin1String("fc_recovery_file.xml"))) {
            XmlConfig cfg = readXmlFile(info.xmlFile);

            if (cfg.contains(QString::fromLatin1("Label"))) {
                info.label = cfg[QString::fromLatin1("Label")];
            }

            if (cfg.contains(QString::fromLatin1("FileName"))) {
                info.fileName = cfg[QString::fromLatin1("FileName")];
            }

            if (cfg.contains(QString::fromLatin1("Status"))) {
                QString status = cfg[QString::fromLatin1("Status")];
                if (status == QLatin1String("Deprecated"))
                    info.status = DocumentRecoveryPrivate::Overage;
                else if (status == QLatin1String("Success"))
                    info.status = DocumentRecoveryPrivate::Success;
                else if (status == QLatin1String("Failure"))
                    info.status = DocumentRecoveryPrivate::Failure;
            }

            if (info.status == DocumentRecoveryPrivate::Created) {
                // compare the modification dates
                QFileInfo fileInfo(info.fileName);
                if (!info.fileName.isEmpty() && fileInfo.exists()) {
                    QDateTime dateRecv = QFileInfo(file).lastModified();
                    QDateTime dateProj = fileInfo.lastModified();
                    if (dateRecv < dateProj) {
                        info.status = DocumentRecoveryPrivate::Overage;
                        writeRecoveryInfo(info);
                        qWarning() << "Ignore recovery file " << file.toUtf8()
                            << " because it is older than the project file" << info.fileName.toUtf8() << "\n";
                    }
                }
            }
        }
    }

    return info;
}

DocumentRecoveryPrivate::XmlConfig DocumentRecoveryPrivate::readXmlFile(const QString& fn) const
{
    DocumentRecoveryPrivate::XmlConfig cfg;
    QDomDocument domDocument;
    QFile file(fn);
    if (!file.open(QFile::ReadOnly))
        return cfg;

    QString errorStr;
    int errorLine;
    int errorColumn;

    if (!domDocument.setContent(&file, true, &errorStr, &errorLine,
                                &errorColumn)) {
        return cfg;
    }

    QDomElement root = domDocument.documentElement();
    if (root.tagName() != QLatin1String("AutoRecovery")) {
        return cfg;
    }

    file.close();

    QVector<QString> filter;
    filter << QString::fromLatin1("Label");
    filter << QString::fromLatin1("FileName");
    filter << QString::fromLatin1("Status");

    QDomElement child;
    if (!root.isNull()) {
        child = root.firstChildElement();
        while (!child.isNull()) {
            QString name = child.localName();
            QString value = child.text();
            if (std::find(filter.begin(), filter.end(), name) != filter.end())
                cfg[name] = value;
            child = child.nextSiblingElement();
        }
    }

    return cfg;
}

#include "moc_DocumentRecovery.cpp"
