# MPL WIDGETS

# Imports
from PyQt5 import QtWidgets
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as Canvas
import matplotlib
from matplotlib.widgets import Slider, Button, RadioButtons
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

# Ensure using PyQt5 backend
matplotlib.use('QT5Agg')

# Matplotlib canvas class to create figure
class MplCanvas(Canvas):
    def __init__(self):
        title = 'Zeeman slower - magnets position OPTIMIZER'
        
        self.fig=plt.figure(layout='tight')
        
        self.ax_B,self.ax_B1= self.fig.subplots(nrows=2,sharex=True)  ## Create 2 subplots sharin x axis
            
        Canvas.__init__(self, self.fig)
        Canvas.setSizePolicy(self, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        Canvas.updateGeometry(self)

    
# Matplotlib widget
class MplWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)   # Inherit from QWidget
        self.canvas = MplCanvas()                  # Create canvas object
        self.mpl_toolbar = NavigationToolbar(self.canvas, self)     # Create matplotlib Toolbar
        self.vbl = QtWidgets.QVBoxLayout()         # Set box for plotting
        self.vbl.addWidget(self.mpl_toolbar)       # Add navaigation toolbar
        self.vbl.addWidget(self.canvas)            # add "canvas"
        self.setLayout(self.vbl)



