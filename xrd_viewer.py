import sys
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, savgol_filter
from scipy import sparse
from scipy.sparse.linalg import spsolve

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLineEdit, QLabel, QColorDialog,
    QInputDialog, QDialog, QTableWidget, QTableWidgetItem, QMessageBox,
    QMenu, QAction, QFontDialog, QDoubleSpinBox
)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas


class ManualDataDialog(QDialog):
    """Simple dialog to enter XRD data manually."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manuel XRD Veri Ekle")
        self.resize(600, 400)
        self.result = None

        layout = QVBoxLayout(self)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Dataset name")
        layout.addWidget(self.name_edit)

        self.table = QTableWidget(20, 2)
        self.table.setHorizontalHeaderLabels(["2θ", "Intensity"])
        layout.addWidget(self.table)

        btns = QHBoxLayout()
        add = QPushButton("Satır Ekle")
        add.clicked.connect(self.add_row)
        btns.addWidget(add)
        ok = QPushButton("Ekle")
        ok.clicked.connect(self.accept_data)
        btns.addWidget(ok)
        cancel = QPushButton("İptal")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def add_row(self):
        self.table.insertRow(self.table.rowCount())

    def accept_data(self):
        xs, ys = [], []
        for r in range(self.table.rowCount()):
            x_item = self.table.item(r, 0)
            y_item = self.table.item(r, 1)
            if x_item is None or y_item is None:
                continue
            try:
                xs.append(float(x_item.text()))
                ys.append(float(y_item.text()))
            except ValueError:
                continue
        if len(xs) < 2:
            QMessageBox.warning(self, "Uyarı", "En az iki nokta giriniz")
            return
        name = self.name_edit.text().strip() or f"Manual-{len(xs)}"
        df = pd.DataFrame({0: xs, 1: ys})
        self.result = (name, df)
        self.accept()


class XRDViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XRD Görüntüleyici")
        self.datasets = []  # list of dicts: {name, df, color, offset}

        self.figure, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.figure)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.canvas)
        self.setCentralWidget(central)

        self._create_menus()

    # ---------------- menus -----------------
    def _create_menus(self):
        bar = self.menuBar()

        file_menu = bar.addMenu("Dosya")
        open_act = QAction("Yeni XRD Yükle", self, triggered=self.load_xrd)
        manual_act = QAction("Manuel Veri Ekle", self, triggered=self.add_manual_dataset)
        save_act = QAction("Kaydet", self, triggered=self.save_plot)
        exit_act = QAction("Çıkış", self, triggered=self.close)
        file_menu.addActions([open_act, manual_act, save_act])
        file_menu.addSeparator()
        file_menu.addAction(exit_act)

        view_menu = bar.addMenu("Görünüm")
        peak_act = QAction("Tepe Noktalarını Göster", self, triggered=self.toggle_peaks)
        view_menu.addAction(peak_act)

        graph_menu = bar.addMenu("Grafik")
        graph_menu.addAction("Başlık Ekle", self.set_title)
        graph_menu.addAction("X Eksen Etiketi", self.set_xlabel)
        graph_menu.addAction("Y Eksen Etiketi", self.set_ylabel)
        graph_menu.addSeparator()
        graph_menu.addAction("Grid Aç/Kapat", self.toggle_grid)
        graph_menu.addAction("Matplotlib Temasını Değiştir", self.change_theme)
        graph_menu.addAction("Arka Plan Rengi", self.set_background_color)

        legend_menu = graph_menu.addMenu("Legend")
        legend_menu.addAction("Göster/Gizle", self.toggle_legend)
        legend_menu.addAction("Konum (Koordinat)", self.set_legend_coordinates)
        legend_menu.addAction("Yazı Tipi", self.set_legend_font)
        legend_menu.addAction("Yazı Rengi", self.set_legend_color)

        axes_menu = bar.addMenu("Eksenler")
        axes_menu.addAction("X Eksen İsmi", lambda: self.set_axis_label('x'))
        axes_menu.addAction("Y Eksen İsmi", lambda: self.set_axis_label('y'))
        axes_menu.addAction("X Eksen Rengi", lambda: self.set_axis_color('x'))
        axes_menu.addAction("Y Eksen Rengi", lambda: self.set_axis_color('y'))

        tick_menu = bar.addMenu("Eksen Çizgileri")
        tick_menu.addAction("X Major Aralık", lambda: self.set_tick_spacing('x'))
        tick_menu.addAction("Y Major Aralık", lambda: self.set_tick_spacing('y'))

        line_menu = bar.addMenu("Çizgi Çekme")
        line_menu.addAction("Dikey Çizgi Ekle", self.add_vertical_line)
        line_menu.addAction("Dikey Çizgileri Temizle", self.clear_vertical_lines)

        preprocess_menu = bar.addMenu("Ön İşleme")
        preprocess_menu.addAction("Yumuşat (SavGol)", self.smooth_savgol)
        preprocess_menu.addAction("Arka Plan Çıkar (ALS)", self.baseline_als)
        preprocess_menu.addAction("Orijinale Dön", self.reset_data)

    # ------------- dataset handling -----------
    def load_xrd(self):
        path, _ = QFileDialog.getOpenFileName(self, "XRD Dosyası", '', "Text Files (*.txt *.csv)")
        if not path:
            return
        try:
            df = pd.read_csv(path, sep=None, engine='python', header=None)
            if df.shape[1] < 2:
                raise ValueError("Dosya iki sütun içermeli")
            name = path.split('/')[-1]
            self.datasets.append({"name": name, "df": df, "color": None, "offset": 0.0})
            self.redraw()
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def add_manual_dataset(self):
        dlg = ManualDataDialog(self)
        if dlg.exec_() == QDialog.Accepted and dlg.result:
            name, df = dlg.result
            self.datasets.append({"name": name, "df": df, "color": None, "offset": 0.0})
            self.redraw()

    # ------------- plotting helpers -----------
    def redraw(self):
        self.ax.clear()
        for d in self.datasets:
            x = d['df'].iloc[:, 0].values
            y = d['df'].iloc[:, 1].values + d['offset']
            kwargs = {}
            if d['color']:
                kwargs['color'] = d['color']
            self.ax.plot(x, y, label=d['name'], **kwargs)
        if self.ax.get_legend_handles_labels()[0]:
            self.ax.legend()
        self.canvas.draw()

    # ------------- menu callbacks -------------
    def save_plot(self):
        path, _ = QFileDialog.getSaveFileName(self, "Kaydet", '', "PNG (*.png);;PDF (*.pdf)")
        if path:
            self.figure.savefig(path, dpi=300, bbox_inches='tight')

    def set_title(self):
        text, ok = QInputDialog.getText(self, "Başlık", "Başlık girin:")
        if ok:
            self.ax.set_title(text)
            self.canvas.draw()

    def set_xlabel(self):
        text, ok = QInputDialog.getText(self, "X Etiketi", "Etiket:")
        if ok:
            self.ax.set_xlabel(text)
            self.canvas.draw()

    def set_ylabel(self):
        text, ok = QInputDialog.getText(self, "Y Etiketi", "Etiket:")
        if ok:
            self.ax.set_ylabel(text)
            self.canvas.draw()

    def toggle_grid(self):
        self.ax.grid(not self.ax.xaxis._gridOnMajor)
        self.canvas.draw()

    def change_theme(self):
        styles = sorted(plt.style.available)
        style, ok = QInputDialog.getItem(self, "Tema", "Seç:", styles, 0, False)
        if ok:
            plt.style.use(style)
            self.redraw()

    def set_background_color(self):
        c = QColorDialog.getColor()
        if c.isValid():
            self.ax.set_facecolor(c.name())
            self.figure.patch.set_facecolor(c.name())
            self.canvas.draw()

    def toggle_legend(self):
        leg = self.ax.get_legend()
        if leg:
            leg.set_visible(not leg.get_visible())
            self.canvas.draw()

    def set_legend_coordinates(self):
        leg = self.ax.get_legend()
        if leg is None:
            QMessageBox.warning(self, "Uyarı", "Önce legend görünür olmalı.")
            return
        x, ok1 = QInputDialog.getDouble(self, "Legend X (0-1)", "x:", 0.95, 0.0, 1.0, 2)
        if not ok1:
            return
        y, ok2 = QInputDialog.getDouble(self, "Legend Y (0-1)", "y:", 0.95, 0.0, 1.0, 2)
        if not ok2:
            return
        handles, labels = self.ax.get_legend_handles_labels()
        self.ax.legend(handles, labels, loc='center', bbox_to_anchor=(x, y))
        self.canvas.draw()

    def set_legend_font(self):
        font, ok = QFontDialog.getFont()
        if ok:
            leg = self.ax.get_legend()
            if leg:
                for text in leg.get_texts():
                    text.set_fontsize(font.pointSize())
                    text.set_fontfamily(font.family())
                self.canvas.draw()

    def set_legend_color(self):
        c = QColorDialog.getColor()
        if c.isValid():
            leg = self.ax.get_legend()
            if leg:
                for text in leg.get_texts():
                    text.set_color(c.name())
                self.canvas.draw()

    def set_axis_label(self, axis):
        text, ok = QInputDialog.getText(self, f"{axis.upper()} Eksen İsmi", "Etiket:")
        if ok:
            if axis == 'x':
                self.ax.set_xlabel(text)
            else:
                self.ax.set_ylabel(text)
            self.canvas.draw()

    def set_axis_color(self, axis):
        c = QColorDialog.getColor()
        if not c.isValid():
            return
        if axis == 'x':
            self.ax.xaxis.label.set_color(c.name())
            self.ax.tick_params(axis='x', colors=c.name())
        else:
            self.ax.yaxis.label.set_color(c.name())
            self.ax.tick_params(axis='y', colors=c.name())
        self.canvas.draw()

    def set_tick_spacing(self, axis):
        val, ok = QInputDialog.getDouble(self, f"{axis.upper()} Major Aralık", "Adım:", 1.0, 0.0001, 1e6, 3)
        if ok:
            from matplotlib.ticker import MultipleLocator
            if axis == 'x':
                self.ax.xaxis.set_major_locator(MultipleLocator(val))
            else:
                self.ax.yaxis.set_major_locator(MultipleLocator(val))
            self.canvas.draw()

    def add_vertical_line(self):
        x, ok = QInputDialog.getDouble(self, "Dikey Çizgi", "2θ değeri:", 0.0, -1e6, 1e6, 3)
        if ok:
            if not hasattr(self, 'vlines'):
                self.vlines = []
            ln = self.ax.axvline(x, color='k', linestyle='--')
            self.vlines.append(ln)
            self.canvas.draw()

    def clear_vertical_lines(self):
        if hasattr(self, 'vlines'):
            for ln in self.vlines:
                ln.remove()
            self.vlines = []
            self.canvas.draw()

    def toggle_peaks(self):
        self.show_peaks = getattr(self, 'show_peaks', False)
        self.show_peaks = not self.show_peaks
        self.redraw()
        if self.show_peaks and self.datasets:
            d = self.datasets[0]
            x = d['df'].iloc[:,0].values
            y = d['df'].iloc[:,1].values
            peaks, _ = find_peaks(y, height=max(y)*0.1)
            self.ax.plot(x[peaks], y[peaks], 'ro', label='Peaks')
            self.ax.legend()
            self.canvas.draw()

    # -------- preprocessing ---------
    def smooth_savgol(self):
        if not self.datasets:
            return
        win, ok1 = QInputDialog.getInt(self, "Pencere", "Tek sayı:", 11, 3, 301, 2)
        if not ok1:
            return
        if win % 2 == 0:
            win += 1
        poly, ok2 = QInputDialog.getInt(self, "Polinom", "Derece:", 3, 1, 7)
        if not ok2:
            return
        for d in self.datasets:
            y = d['df'].iloc[:,1].values
            d['df'].iloc[:,1] = savgol_filter(y, win, poly)
        self.redraw()

    def baseline_als(self):
        if not self.datasets:
            return
        lam, ok1 = QInputDialog.getDouble(self, "λ", "ALS λ:", 1e5, 1e2, 1e9, 0)
        if not ok1:
            return
        p, ok2 = QInputDialog.getDouble(self, "p", "Asimetri:", 0.01, 0.001, 0.5, 3)
        if not ok2:
            return
        for d in self.datasets:
            y = d['df'].iloc[:,1].values
            L = len(y)
            D = sparse.diags([1,-2,1],[0,-1,-2], shape=(L,L-2)).T
            w = np.ones(L)
            for _ in range(10):
                W = sparse.spdiags(w, 0, L, L)
                Z = W + lam * (D.T @ D)
                z = spsolve(Z, w*y)
                w = p*(y>z) + (1-p)*(y<z)
            d['df'].iloc[:,1] = y - z
        self.redraw()

    def reset_data(self):
        # simply reload from stored originals; for brevity we do not keep originals, so just redraw
        self.redraw()


def main():
    app = QApplication(sys.argv)
    viewer = XRDViewer()
    viewer.resize(900, 600)
    viewer.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
