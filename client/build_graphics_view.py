import logging
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsProxyWidget
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QRectF
from PySide6.QtGui import QCursor, QColor, Qt

logger = logging.getLogger(__name__)

class BuildGraphicsView(QGraphicsView):
    def __init__(self, build_widget, parent=None):
        super().__init__(parent)
        self.build_widget = build_widget
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.proxy = QGraphicsProxyWidget()
        self.proxy.setWidget(build_widget)
        self.scene.addItem(self.proxy)

        self.setSceneRect(QRectF(build_widget.rect()))
        self.setFixedSize(build_widget.size())
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.setCursor(QCursor(Qt.PointingHandCursor))
        logger.info(f"BuildGraphicsView для {build_widget.version}: кнопки должны быть видны")

        self.setup_animations()

    def setup_animations(self):
        self.anim_group = QParallelAnimationGroup()

        color_anim = QPropertyAnimation(self.build_widget, b"bg_color")
        color_anim.setDuration(350)
        color_anim.setEasingCurve(QEasingCurve.InOutCubic)

        scale_anim = QPropertyAnimation(self.proxy, b"scale")
        scale_anim.setDuration(350)
        scale_anim.setEasingCurve(QEasingCurve.InOutCubic)

        self.anim_group.addAnimation(color_anim)
        self.anim_group.addAnimation(scale_anim)

    def enterEvent(self, event):
        self.anim_group.stop()
        self.anim_group.animationAt(0).setStartValue(self.build_widget.get_bg_color())
        self.anim_group.animationAt(0).setEndValue(QColor("#353535"))
        self.anim_group.animationAt(1).setStartValue(self.proxy.scale())
        self.anim_group.animationAt(1).setEndValue(1.03)
        self.anim_group.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.anim_group.stop()
        self.anim_group.animationAt(0).setStartValue(self.build_widget.get_bg_color())
        self.anim_group.animationAt(0).setEndValue(QColor("#252525"))
        self.anim_group.animationAt(1).setStartValue(self.proxy.scale())
        self.anim_group.animationAt(1).setEndValue(1.0)
        self.anim_group.start()
        super().leaveEvent(event)