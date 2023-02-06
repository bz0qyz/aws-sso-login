import sys
from PyQt6 import QtGui
from PyQt6.QtCore import QSize, Qt, QByteArray
from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QButtonGroup ,QGridLayout, QCheckBox, QStatusBar
from lib.icon import ICON_BASE64

QApp = QApplication(sys.argv)


class MainWindow(QMainWindow):
    def __init__(self, **kwargs):
        super().__init__()
        self.canceled = True
        self.args = kwargs
        self.options = {}
        self.layout = QGridLayout()

        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(QByteArray.fromBase64(ICON_BASE64))
        QApp.setWindowIcon(QtGui.QIcon(QtGui.QIcon(pixmap)))

        # Set the central widget of the Window.
        widget = QWidget(self)
        self.setCentralWidget(widget)

        self.setFixedSize(QSize(300, 300))
        self.setWindowTitle(f"{self.args['app']['description']}")

        optionsgroup = QGroupBox("Login Options")
        options_layout = QVBoxLayout()
        optionsgroup.setLayout(options_layout)
        for key, meta in self.args['arguments']["options"].items():
            if meta["enabled"]:
                label = meta["label"]
                value = getattr(self.args['options'], key)
                if meta["invert"]:
                    value = not value
                # print(f"Key: {key}, Value: {value}. enabled: {meta['enabled']}")
                self.options[key] = QCheckBox(f"{label}", checked=value)
                self.options[key].setToolTip(meta["help"])
                self.options[key].stateChanged.connect(self.checkbox_changed)
                options_layout.addWidget(self.options[key])

        # configgroup = QGroupBox("Configuration")
        # config_layout = QVBoxLayout()
        # configgroup.setLayout(config_layout)


        buttons_layout = QHBoxLayout()
        self.buttongroup = QButtonGroup()
        self.buttongroup.buttonClicked.connect(self.button_clicked)
        button_cancel = QPushButton("Cancel")
        button_start = QPushButton("Start")
        self.buttongroup.addButton(button_cancel, 0)
        self.buttongroup.addButton(button_start, 1)
        self.buttongroup.setExclusive(True)
        
        buttons_layout.addWidget(self.buttongroup.button(0))
        buttons_layout.addWidget(self.buttongroup.button(1))

        self.layout.addWidget(optionsgroup, 0, 0,1,2)
        # self.layout.addWidget(optionsgroup, 0, 0)
        # self.layout.addWidget(configgroup, 0, 1)
        self.layout.addLayout(buttons_layout, 1, 0, 1, 2)
        widget.setLayout(self.layout)

        self.statusbar = QStatusBar()
        self.statusbar.showMessage(f"{self.args['app']['name']} v{self.args['app']['version']}")
        self.statusbar.setToolTip(f"Author: {self.args['app']['author']}")
        self.statusbar.layout().setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setStatusBar(self.statusbar)

    def button_clicked(self, button):
        """ Process the button clicks. """
        if button.text() == "Cancel":
            QApp.quit()
        elif button.text() == "Start":
            self.canceled = False
            QApp.quit()
    def checkbox_changed(self, state):
        """ Process the checkbox clicks. """
        for checkbox in self.options:
            value = self.options[checkbox].isChecked()
            if self.args['arguments']["options"][checkbox]["invert"]:
                value = not value
            setattr(self.args['options'], checkbox, value)