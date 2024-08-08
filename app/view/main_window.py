# coding: utf-8
from pathlib import Path

import darkdetect
from PySide6.QtCore import QSize, QUrl, QThread, Signal, QTimer
from PySide6.QtGui import QIcon, QDesktopServices
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import QApplication
from loguru import logger
from qfluentwidgets import FluentIcon as FIF, setTheme, Theme
from qfluentwidgets import NavigationItemPosition, MessageBox, MSFluentWindow, SplashScreen

from .setting_interface import SettingInterface
from .task_interface import TaskInterface
from ..common.config import VERSION, YEAR, AUTHOR, AUTHOR_URL, cfg
from ..common.custom_socket import GhostDownloaderSocketServer
from ..common.signal_bus import signalBus
from ..components.add_task_dialog import AddTaskOptionDialog


class ThemeChangedListener(QThread):
    themeChanged = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        darkdetect.listener(self.themeChanged.emit)


class MainWindow(MSFluentWindow):

    def __init__(self):
        super().__init__()
        self.initWindow()

        # create sub interface
        self.taskInterface = TaskInterface(self)
        self.settingInterface = SettingInterface(self)
        # self.debugInterface = DebugInterface(self)

        # add items to navigation interface
        self.initNavigation()

        # 创建检测主题色更改线程
        self.themeChangedListener = ThemeChangedListener(self)
        self.themeChangedListener.themeChanged.connect(self.toggleTheme)
        self.themeChangedListener.start()

        # createUnfinishedTask
        historyFile = Path("./Ghost Downloader 记录文件")
        # 未完成任务记录文件格式示例: [{"url": "xxx", "fileName": "xxx", "filePath": "xxx", "blockNum": x, "status": "xxx"}]
        if historyFile.exists():
            with open(historyFile, 'r', encoding='utf-8') as f:
                unfinishedTaskInfo = f.readlines()
                logger.debug(f"Unfinished Task is following:{unfinishedTaskInfo}")
                for i in unfinishedTaskInfo:
                    if i:  # 避免空行
                        i = eval(i)
                        signalBus.addTaskSignal.emit(i['url'], i['filePath'], i['blockNum'], i['fileName'], i["status"], None, True)
        else:
            historyFile.touch()

        if cfg.enableBrowserExtension.value == True:
            self.browserExtensionSocket = GhostDownloaderSocketServer(self)
            self.browserExtensionSocket.receiveUrl.connect(lambda x: self.taskInterface.addDownloadTask(x, cfg.downloadFolder.value, cfg.maxBlockNum.value))

        self.splashScreen.finish()

    def toggleTheme(self, callback: str):
        if callback == 'Dark':
            setTheme(Theme.DARK, save=False)
            QTimer.singleShot(100, lambda: self.windowEffect.setMicaEffect(self.winId(), True))
            QTimer.singleShot(200, lambda: self.windowEffect.setMicaEffect(self.winId(), True))
            QTimer.singleShot(300, lambda: self.windowEffect.setMicaEffect(self.winId(), True))

        elif callback == 'Light':
            setTheme(Theme.LIGHT, save=False)

    def initNavigation(self):
        # add navigation items
        self.addSubInterface(self.taskInterface, FIF.DOWNLOAD, "任务列表")
        self.navigationInterface.addItem(
            routeKey='addTaskButton',
            text='新建任务',
            selectable=False,
            icon=FIF.ADD,
            onClick=self.showAddTaskBox,
            position=NavigationItemPosition.TOP,
        )

        # self.addSubInterface(self.debugInterface, FIF.DEVELOPER_TOOLS, "调试信息")
        # add custom widget to bottom
        self.addSubInterface(self.settingInterface, FIF.SETTING, "设置", position=NavigationItemPosition.BOTTOM)

    def initWindow(self):
        self.resize(960, 780)
        self.setWindowIcon(QIcon(':/image/logo.png'))
        self.setWindowTitle('Ghost Downloader')

        # create splash screen
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(106, 106))
        self.splashScreen.raise_()

        desktop = QApplication.screens()[0].availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w//2 - self.width()//2, h//2 - self.height()//2)
        self.show()
        QApplication.processEvents()


    def showAddTaskBox(self):
        w = AddTaskOptionDialog(self)
        w.exec()

    def closeEvent(self, event):
        super().closeEvent(event)

        self.themeChangedListener.terminate()

        for i in self.taskInterface.cards:
            if i.status == 'working':
                for j in i.task.workers:
                    try:
                        j.file.close()
                    except AttributeError as e:
                        logger.info(f"Task:{i.task.fileName}, users operate too quickly!, thread {i} error: {e}")
                    except Exception as e:
                        logger.warning(
                            f"Task:{i.task.fileName}, it seems that cannot cancel thread {i} occupancy of the file, error: {e}")
                    j.terminate()
                i.task.terminate()

        event.accept()
