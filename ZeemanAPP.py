
# -*- coding: utf-8 -*-
"""
Created on Fri Dec  7 21:04:55 2018

@author: elcortex (icortes@roa.es) / jcafranga (@roa.es) with Gemini AI help

"""
import sys
from ZeemanGUI import Ui_MainWindow
import ZeemanGUI
from PyQt5.QtWidgets import *
from PyQt5.QtWidgets import QAbstractSpinBox 
from PyQt5.QtCore import pyqtSignal, QObject, Qt, QCoreApplication, QEvent, QThread # For signals
from zeeman_package.ZeemanCore import ZeemanCore
from PyQt5 import QtCore, QtWidgets # For the QMessageBox
from PyQt5.QtGui import QIcon#  QIcon to laod icon 
import numpy as np
from configparser import ConfigParser  #Carga fichero ini
#Time
from datetime import datetime as dtm
# import time 
import os
import matplotlib
from colorama import Fore, Style, init
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Verdana', 'sans-serif']

import h5py
import traceback
import copy
import ctypes
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import matplotlib.image as mpimg

class WorkerThread(QThread):
    """
    Generic Worker Thread to run any function in background.
    It expects a function that accepts a 'progress_callback' argument.
    """
    progress_signal = pyqtSignal(int) # Emits % (0-100)
    finished_signal = pyqtSignal()    # Emits when done
    error_signal = pyqtSignal(str)    # Emits if something crashes

    def __init__(self, function_to_run, *args, **kwargs):
        super().__init__()
        self.function_to_run = function_to_run # We store the FUNCTION itself
        self.args = args
        self.kwargs = kwargs

    def run(self):
        """
        Runs the stored function passing the arguments and the signal emitter.
        """
        try:
            # We call the function directly (because we passed self.zeeman.optimal_position)
            # We inject our signal emitter as the 'progress_callback'
            self.function_to_run(*self.args, **self.kwargs, progress_callback=self.progress_signal.emit)
            
            self.finished_signal.emit()
            
        except Exception as e:
            # If calculation fails, we catch the error
            import traceback
            traceback.print_exc()
            self.error_signal.emit(str(e))

class LoadingScreen(QWidget):
    """
    Custom widget to display a loading veil over the main application.
    It intercepts parent resize events to stay full-sized.
    """
    cancel_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        
        # 0. Install Event Filter
        # This allows the LoadingScreen to "spy" on the parent window resizing events
        if self.parent:
            self.parent.installEventFilter(self)

        # 1. Semitransparent configuration
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False) # Blocks mouse clicks
        self.setAttribute(Qt.WA_NoSystemBackground, False)
        # RGBA background: White with alpha=150 (approx 60% opacity)
        self.setStyleSheet("background-color: rgba(255, 255, 255, 150);") 

        # 2. Main Layout (Centers the content)
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)
        
        # 3. Content Container (Frame)
        # This frame holds the text and bar, with a solid background
        self.frame = QFrame()
        self.frame.setStyleSheet("""
            QFrame {
                background-color: white; 
                border-radius: 10px; 
                padding: 10px;
                border: 1px solid gray;
            }
        """)
        self.frame_layout = QVBoxLayout(self.frame)
        
        # 4. Text Label
        self.label = QLabel("Calculating...\nPlease wait.")
        self.label.setAlignment(Qt.AlignCenter)
        # Remove border from label to avoid double borders inside the frame
        self.label.setStyleSheet("color: red; font-weight: bold; font-size: 14px; border: none; background-color: transparent;")

        # 5. Progress Bar
        self.progress = QProgressBar()
        self.progress.setStyleSheet("QProgressBar { min-width: 200px; }")
        self.progress.setFixedHeight(10)
        self.progress.setAlignment(Qt.AlignCenter)
        # Range (0, 0) sets "Indeterminate mode" (infinite moving bar)
        self.progress.setRange(0, 0) 
        
        # 6. Cancel Button
        self.btn_cancel = QPushButton("Stop Calculation")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #ffcccc; 
                color: red; 
                border: 1px solid red; 
                border-radius: 5px;
                padding: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff9999;
            }
        """)
        self.btn_cancel.clicked.connect(self.cancel_process)
        
        # Add widgets to the internal frame
        self.frame_layout.addWidget(self.label)
        self.frame_layout.addWidget(self.progress)
        self.frame_layout.addWidget(self.btn_cancel)
        
        # Add frame to the main veil layout
        self.layout.addWidget(self.frame)
        
        self.hide() # Hidden by default

    def eventFilter(self, source, event):
        """
        Catches the parent's resize events to automatically resize this overlay.
        """
        if source == self.parent and event.type() == QEvent.Resize:
            # If parent resizes, force this widget to match the new size
            self.resize(event.size())
        
        return super().eventFilter(source, event)

    def show_loading(self, text="Calculating...", without_button=False):
        """
        Displays the loading screen.
        """
        # Configure button visibility based on arguments
        if not without_button:
            self.btn_cancel.show()
            self.btn_cancel.setEnabled(True)
            self.btn_cancel.setText("Stop Calculation")
        else:
            self.btn_cancel.hide()
        
        self.label.setText(text)
        
        self.progress.setRange(0, 100) 
        self.progress.setValue(0)
        
        # Force size update before showing to avoid flicker
        if self.parent:
            self.resize(self.parent.size())
            
        self.show()
        self.raise_() # Bring to front
        QApplication.processEvents() # Refresh GUI immediately
        
    def update_progress(self, value):
        """
        Updates the progress bar value.
        """
        self.progress.setValue(value)
        
    def cancel_process(self):
        """
        Triggered when user clicks 'Stop Calculation'.
        """
        self.label.setText("Stopping process...\nPlease wait.")
        self.btn_cancel.setText("Stopping...")
        self.btn_cancel.setEnabled(False) # Prevent double clicking
        QApplication.processEvents() 
        self.cancel_signal.emit()
        
    def stop_loading(self):
        """
        Hides the loading screen.
        """
        self.hide()
    

class app_gui(QMainWindow,ZeemanGUI.Ui_MainWindow):
      
    def __init__(self):
        init(autoreset=True)
        print('-->> Entering Zeeman APP __ini__')
        # Create the main window
        super(app_gui, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)  
        
       # =========================================================================
        # AUTO-LAYOUT WITH STICKY FOOTER LOGOS
        # =========================================================================
        
        # 1. Basic Window Configuration
        self.setMinimumSize(1280, 820)
        self.setMaximumSize(16777215, 16777215)

        # 2. Create the Left Panel and assign a Vertical Layout
        self.left_panel = QWidget()
        self.left_panel.setFixedWidth(290) 
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(0, 0, 0, 10) # Slight bottom margin (10px)
        self.left_layout.setSpacing(0)

        # 3. Create a container for TOP CONTROLS (Spinboxes, Buttons, etc.)
        # This acts as a fixed canvas to preserve your original coordinate design.
        self.top_controls_container = QWidget()
        # Set a fixed height sufficient to fit all top buttons (e.g., 600px).
        # If bottom buttons are cut off, increase this number.
        self.top_controls_container.setFixedSize(290, 900) 

        # 4. Child Classification (Re-parenting)
        children_list = self.ui.centralwidget.children()
        
        # List to store the specific bottom logos found
        bottom_logos = []
        
        # --- DEFINE REAL OBJECT NAMES FOR BOTTOM LOGOS HERE ---
        bottom_logo_names = ["label_3", "label_4"] 

        for child in children_list:
            # Ignore the main graph widget and layouts
            if child != self.ui.widget and not isinstance(child, QLayout):
                
                # A) If it is one of the bottom logos...
                if child.objectName() in bottom_logo_names:
                    bottom_logos.append(child)
                
                # B) If it is any other control (Spinbox, Button, normal Label)...
                else:
                    original_pos = child.pos()
                    child.setParent(self.top_controls_container) # Move to top container
                    child.move(original_pos) # Maintain exact original position
                    child.show()

        # 5. Assemble the Vertical Layout for the Left Panel
        self.left_layout.addWidget(self.top_controls_container)
        self.left_layout.addStretch() # The "spacer" that pushes everything else to the bottom
        
        # --- IMPROVED BOTTOM LOGOS LAYOUT ---
        logos_layout = QHBoxLayout() 
        logos_layout.setContentsMargins(10, 5, 10, 5) # Margins around logos
        logos_layout.setSpacing(10) # Space between the two logos
        
        for logo in bottom_logos:
            # 1. Configure logo to scale properly
            logo.setScaledContents(True)
            
            # 2. Limit maximum dimensions
            # This prevents vertical stretching/deformation
            logo.setMaximumHeight(120) 
            logo.setMaximumWidth(120) 
            
            # 3. Size Policy: Try to maintain aspect ratio
            # (Note: QLabel sometimes ignores this with scaledContents, but it helps)
            logo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

            # 4. Add to layout
            logos_layout.addWidget(logo)
            logo.setParent(self.left_panel)
            logo.show()
            
        # Add the logos layout to the bottom of the left panel
        self.left_layout.addLayout(logos_layout)

        # 6. Main Layout (Horizontal)
        self.main_layout = QHBoxLayout(self.ui.centralwidget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.main_layout.addWidget(self.left_panel)
        self.main_layout.addWidget(self.ui.widget)
        
        # Ensure the graph widget expands to fill available space
        self.ui.widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # =========================================================================
        # END OF AUTO-LAYOUT
        # =========================================================================
        
               
        # self.setWindowTitle('Zeeman slower - magnets position OPTIMIZER')
        # Creates object with initial parameters.
        self.zeeman = ZeemanCore()
        
        # We prepare the veil
        self.loading_screen = LoadingScreen(self)
        # self.loading_screen.cancel_signal.connect(self.break_simulations)
        self.prepare_lineEdits()
        
        # Fixed values
        self.npm_min = 4    # Number of minimum magnets pairs
        self.npm_max = 20   # Number of maximum magnets pairs
        self.initial_pos_flag=False


        
        # Canvas for plot
        self.pw = self.ui.widget.canvas  # widget -> MPlWidget (2 subplots, sharing x axis, with navigation toolbar)
        # Telling zeeman object the figure and subplots identifiers
        self.zeeman.create_subplots(self.pw.ax_B,self.pw.ax_B1,self.pw)

        # Signal - Buttons
        self.ui.pushButton_Find.clicked.connect(self.position_ini)   # Initial position
        self.ui.pushButton_Find_2.clicked.connect(self.position_opt)    # Optimize magnets position
        self.ui.pushButton_2D_magnetic_field.clicked.connect(self.generate_2Dplot)  # Generate plot with 2D Bfield
        self.ui.pushButton_atomic_kinetics.clicked.connect(self.run_atomic_kinetics)  # ¿?
        self.ui.pushButton_save_file.clicked.connect(self.file_generate) # Save file with main data of simulation
        self.ui.pushButton_load_file.clicked.connect(self.load_data_from_file) # Save file with main data of simulation
        self.ui.pushButton_Update.clicked.connect(self.load_GUI_data)
        self.ui.comboBox_Atom_Ion.activated.connect(self.atomic_parameters) # Load data for atomic species
        
        # •	Hide buttons not usable at the opening.
        self.ui.pushButton_Find_2.hide()
        self.ui.pushButton_2D_magnetic_field.hide()
        self.ui.pushButton_atomic_kinetics.hide()
        self.ui.pushButton_save_file.hide()
        self.ui.pushButton_load_file.hide()
        self.ui.pushButton_Update.hide()
        self.ui.pushButton_Update.setStyleSheet("background-color: #AFEEEE;")
               
        self.primer =True
        self.test = False
        
        # Default value for Atom/Ion combo box
        self.search_Atom_Ion = '87Sr'

        # Read data from config.ini file and updates GUI
        self.load_initial_data()
        
        # Create spinboxes                
        self.create_spinboxes()
        # print('<<--EXITING Zeeman APP __ini__')
        
        self.check_values()
        
        if self.error == False:
            self.zeeman.prepare_data()
        else:
            self.values_error = 'Please, make proper corrections to values in config.ini.'
            self.show_error()
            sys.exit()
        
        # Defines what happens for each modification of each textbox edition.
        
        self.ui.lineEdit_Number_of_magnets.editingFinished.connect(self.manage_buttons_update)
        self.ui.lineEdit_Power_laser.editingFinished.connect(self.manage_buttons_update)
        self.ui.lineEdit_Tmagz.editingFinished.connect(self.manage_buttons_update)
        self.ui.lineEdit_V_cap.editingFinished.connect(self.manage_buttons_update)
        self.ui.lineEdit_V_sal.editingFinished.connect(self.manage_buttons_update)
        self.ui.lineEdit_ZS.editingFinished.connect(self.manage_buttons_update)
        self.ui.lineEdit_d0_Mhz.editingFinished.connect(self.manage_buttons_update)
        self.ui.lineEdit_mag_D.editingFinished.connect(self.manage_buttons_update)
        self.ui.lineEdit_mag_H.editingFinished.connect(self.manage_buttons_update)
        self.ui.lineEdit_w0.editingFinished.connect(self.manage_buttons_update)
        
        # =========================================================================
        # TAB ORDER CONFIGURATION
        # =========================================================================
        
        # 1. Define the manual list of the top controls in order
        tab_chain = [
            self.ui.comboBox_Atom_Ion,
            self.ui.pushButton_Update,
            self.ui.lineEdit_Number_of_magnets,
            self.ui.lineEdit_Power_laser,
            self.ui.lineEdit_ZS,
            self.ui.lineEdit_Length_apparatus,
            self.ui.lineEdit_V_cap,
            self.ui.lineEdit_V_sal,
            self.ui.lineEdit_d0_Mhz,
            self.ui.lineEdit_w0,
            self.ui.lineEdit_mag_D,
            self.ui.lineEdit_mag_H,
            self.ui.lineEdit_Tmagz,
            self.ui.pushButton_Find,
            self.ui.pushButton_2D_magnetic_field,
            self.ui.pushButton_Find_2,
            self.ui.pushButton_atomic_kinetics,
            self.ui.pushButton_save_file,
            self.ui.pushButton_load_file
        ]

        # 2. Automatically add the H and V spinboxes (1 to 20)
        # We assume names are dSP_H_1 ... dSP_H_20
        for i in range(1, 21):
            # We use getattr to get the object by its name string
            if hasattr(self.ui, f"dSP_H_{i}"):
                tab_chain.append(getattr(self.ui, f"dSP_H_{i}"))
        
        for i in range(1, 21):
            if hasattr(self.ui, f"dSP_V_{i}"):
                tab_chain.append(getattr(self.ui, f"dSP_V_{i}"))

        # 3. Apply the order in a single loop
        for i in range(len(tab_chain) - 1):
            QWidget.setTabOrder(tab_chain[i], tab_chain[i+1])
            
        # Optional: Loop back to start?
        # QWidget.setTabOrder(tab_chain[-1], tab_chain[0])
        
        self.draw_initial_logos()
        
        print('<<--EXITING Zeeman APP __ini__')
        
    # ----------------------------------------------------------------------
    # 1. Helper Function (With forced transparency)
    # ----------------------------------------------------------------------
    def place_centered_image(self, ax, filename, zoom=0.5):
        try:
            arr_img = mpimg.imread(filename)
            imagebox = OffsetImage(arr_img, zoom=zoom)
            
            # BOX PROPERTIES: Force invisibility (alpha=0)
            # This eliminates any "white box" around the image
            ab = AnnotationBbox(imagebox, (0.5, 0.5), 
                                xycoords='axes fraction', 
                                frameon=False,        # No border
                                box_alignment=(0.5, 0.5),
                                bboxprops=dict(facecolor='none', edgecolor='none', alpha=0)) 
            
            ax.add_artist(ab)
            
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            ax.text(0.5, 0.5, "LOGO ERROR", ha='center', va='center')

    # ----------------------------------------------------------------------
    # 2. Main Function (Adjusting margins to the limit)
    # ----------------------------------------------------------------------
    def draw_initial_logos(self):
        # 1. Cleanup
        self.pw.ax_B.clear()
        self.pw.ax_B1.clear()

        # 2. Aesthetic configuration (Black borders, no numbers)
        for ax in [self.pw.ax_B, self.pw.ax_B1]:
            ax.set_xticks([])
            ax.set_yticks([])
            # Transparent axis background so it doesn't look white if something is behind
            ax.patch.set_alpha(0) 
            
            for spine in ax.spines.values():
                spine.set_visible(True)
                spine.set_color('black')
                spine.set_linewidth(0.7) # Slightly thicker for better visibility

        # 3. REMOVE MARGINS (Solution for vertical spacing)
        # hspace=0 makes the top plot touch the bottom one.
        # left/right/top/bottom stick the plots to the window edges.
        self.pw.figure.subplots_adjust(left=0.005, right=0.995, top=0.995, bottom=0.005, hspace=0)

        # 4. Place Logos (Adjust zoom in code if needed)
        self.place_centered_image(self.pw.ax_B, 'logo.jpg', zoom=0.7) 
        self.place_centered_image(self.pw.ax_B1, 'DOZE.png', zoom=0.7)
        
    def break_simulations(self):
        self.zeeman.break_simulations = True
        
    def manage_buttons_update(self):
        '''
            This function will show the update button and hide others to keep 
            app flowing in proper order
        '''
        
        sender = self.sender()
        if sender:
            print(f"DEBUG: manage_buttons_update llamado por: {sender.objectName()}")
        else:
            print("DEBUG: manage_buttons_update llamado manualmente")
            
        self.ui.pushButton_Update.show()
        self.ui.pushButton_Update.setFocus()
        
        self.ui.pushButton_Find.hide()
        self.ui.pushButton_Find_2.hide()
        self.ui.pushButton_2D_magnetic_field.hide()
        self.ui.pushButton_atomic_kinetics.hide()
        self.ui.pushButton_save_file.hide()
      
   
    def prepare_lineEdits(self):
        '''
            We set the properties of the spinboxes in the upper left part of the GUI
            setting their range and number of decimals
        '''
        self.ui.lineEdit_mag_D.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.ui.lineEdit_mag_D.setDecimals(1)
        self.ui.lineEdit_mag_D.setRange(1.0, 100.0)
        
        self.ui.lineEdit_mag_H.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.ui.lineEdit_mag_H.setDecimals(1)
        self.ui.lineEdit_mag_H.setRange(1.0, 30.0)
        
        self.ui.lineEdit_Number_of_magnets.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.ui.lineEdit_Number_of_magnets.setRange(4, 20)

        
        self.ui.lineEdit_Power_laser.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.ui.lineEdit_Power_laser.setDecimals(1)
        self.ui.lineEdit_Power_laser.setRange(1, 1000)
        
        self.ui.lineEdit_Tmagz.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.ui.lineEdit_Tmagz.setRange(100, 3000)       
        
        self.ui.lineEdit_V_cap.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.ui.lineEdit_V_cap.setRange(100, 800)    
        
        self.ui.lineEdit_V_sal.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.ui.lineEdit_V_sal.setRange(0, 100)           
        
        self.ui.lineEdit_ZS.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.ui.lineEdit_ZS.setDecimals(1)
        self.ui.lineEdit_ZS.setRange(10, 50)
        
        self.ui.lineEdit_d0_Mhz.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.ui.lineEdit_d0_Mhz.setDecimals(1)
        self.ui.lineEdit_d0_Mhz.setRange(-1000, -100)
     
        self.ui.lineEdit_w0.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.ui.lineEdit_w0.setDecimals(1)
        self.ui.lineEdit_w0.setRange(1, 50)
        
        self.ui.lineEdit_Length_apparatus.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.ui.lineEdit_Length_apparatus.setDecimals(1)
        self.ui.lineEdit_Length_apparatus.setRange(0, 100)
    
    def check_values(self):
        '''
            Function to check if values setup in GUI or config.ini are valid
        '''
        if self.test==True: print('-->> Entering Zeeman APP check_values')
        if self.test==True: print(self.zeeman.LZ, self.zeeman.mag_diam, self.zeeman.Npm)
        
        self.error = False
        
        # Check magnets size
        if (self.zeeman.Npm < 4) or (self.zeeman.Npm > 20):
            self.values_error='Number of magnets has to be within range 4-20.'
            self.error = True

        # Check number of magnets
        elif (self.zeeman.Npm-2)*self.zeeman.mag_diam > self.zeeman.LZ*1000: # Comparison made in [mm]
            self.values_error='Magnets cannot be arranged within the ZeemanSlower length. Check number of magnets, magnet diameter or length for deceleration.'
            self.error = True
        
        if self.error == True:
            self.ui.pushButton_Find.hide()
            self.ui.pushButton_Find_2.hide()
            self.ui.pushButton_2D_magnetic_field.hide()
            self.ui.pushButton_atomic_kinetics.hide()
            self.ui.pushButton_save_file.hide()
            self.ui.pushButton_load_file.hide()
            self.show_error()
            self.pw.ax_B.clear()
            self.pw.ax_B1.clear()
            self.draw_initial_logos()
            return
            
        else:
            self.ui.pushButton_Find.show()
            self.ui.pushButton_Find.setFocus()

        if self.test==True: print('In end position ini self.error = ', self.error)
        if self.test==True: print('<<--EXITING Zeeman APP check_values')
        return
        

    def show_error(self):
        '''
            Function to show a pop up window wth the error present within the values
        '''
        if self.test==True: print('-->> Entering Zeeman APP show_error')
        msg = QMessageBox()
        msg.setWindowIcon(QIcon('DOZE.ico')) 
        msg.setIcon(QMessageBox.Warning) # Icono de triángulo amarillo
        msg.setWindowTitle('Error')
        msg.setText(self.values_error)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_() # Muestra la ventana y espera a que el usuario pulse OK
        if self.test==True: print('<<--EXITING Zeeman APP show_error')
    
    
    def load_initial_data(self): 
        """ 
            Reads data from config.ini, updates object "zeeman" and GUI
        """
        if self.test==True: print('-->> Entering Zeeman APP load_initial_data()')
        if self.test==True: print("\n ->> Load data from the config.ini file") #TEST 

        #Reads data from config.ini
        configur = ConfigParser()
        configur.read('config.ini')
  
        # Update values read from config.ini
        self.zeeman.Npm = configur.getint('data_initial','Npm')     # Number of pairs of magnets
        # print('Npm ',self.zeeman.Npm)
        self.zeeman.P = configur.getfloat('data_initial','P') / 1000 # Laser power [mW]
        
        self.zeeman.eta = configur.getfloat('data_initial','eta') #Eta parameter for full s_max usage [a.u. 0-1]
        self.zeeman.P = configur.getfloat('data_initial','P') / 1000 # Laser power [mW]
        self.zeeman.LZ = configur.getfloat('data_initial','z')/100  # ZeemanSlower length [cm]
                
        self.zeeman.V_cap = configur.getint('data_initial','V_cap') # Capture velocity [m/s]
        self.zeeman.V_fin = configur.getint('data_initial','V_fin') # Final velocity [m/s]
        
        self.zeeman.d0_Mhz = configur.getfloat('data_initial','d0') # Laser detuning [MHz]
        self.zeeman.Delta0 = self.zeeman.d0_Mhz * 2 * np.pi * 1e6   # Laser detuning [rad/s]
         
        self.zeeman.w0 = configur.getfloat('data_initial','w0') / 1000 # Beam waist: read in [mm], stored in [m] (division factor 1000)
                
        self.zeeman.mag_diam = configur.getfloat('data_initial','mag_diam')  # Magnet diameter [mm]
        self.zeeman.mag_heig = configur.getfloat('data_initial','mag_heig')  # Magnet height [mm]
        self.zeeman.size_mag = (self.zeeman.mag_diam,self.zeeman.mag_heig)   # Magnet size vector as requested by magpylib [m]
        self.zeeman.Tmagz = configur.getint('data_initial','Tmagz')          # Magnet remanescence [mT]
        
        
        #Attributes whitout not shown in GUI
        self.zeeman.ext_tube_radius = configur.getfloat('data_initial','ext_tube_radius') # Distance from axis y=0 to external part of vacuum tub e[mm]
        self.zeeman.safety_margin = configur.getint('data_initial','safety_margin')       #  
        self.zeeman.displ = configur.getfloat('data_initial','displ')   # Minimum distance you can move a magnet [mm] (resolution of 3D printer or manufacturing process)
        self.zeeman.iterations_max = configur.getint('data_initial','max_iters')   # Maximum number of iterations for each magnet optimization process [#]
        self.zeeman.sep_ini = configur.getfloat('data_initial','sep_ini')   # Fixed y distance betweeen magnet 0 and 1 [mm] (slope adaptation at beginning of the slower)
        self.zeeman.sep_last = configur.getfloat('data_initial','sep_last')   # Fixed y distance betweeen last magnet and previous one [mm] (exit speed selection)
        
        
        self.zeeman.N_vel = configur.getint('atomic_kinetics','N_vel')  # Number of velocities to be simulated (from zero to a 10% over Vcap)
        self.zeeman.Nt = int(configur.getfloat('atomic_kinetics','Nt')) # Time vector number of points
        self.zeeman.dt = configur.getfloat('atomic_kinetics','dt')      # Time vector resolution [s]
        self.zeeman.atoms_initial_z_position = configur.getfloat('atomic_kinetics','atoms_initial_z_position')   # z position where atoms are placed at t=0 of simulation time [mm]
        self.zeeman.use_sigma_plus = configur.getboolean('atomic_kinetics','use_sigma_plus') #Consider usage of sigma+ light [Bool]
        
        self.zeeman.B_points = configur.getint('number of points to calculate B','B_points')      # Time vector resolution [s]
        self.zeeman.B_points_additional = configur.getint('number of points to calculate B','B_points_additional')      # Time vector resolution [s]
        self.zeeman.scale_factor_B = configur.getfloat('scale_factor_B','scale_factor_B')      # Time vector resolution [s]
        
        
        # We load the atomic parameters too
        self.atomic_parameters()
        
        self.update_GUI()
        
        if self.test==True: print('<<--EXITING Zeeman APP load_initial_data()')
        
    def atomic_parameters(self):
        """ 
            Reading data from config.ini and converting to used units
        """
        if self.test==True: print('-->> Entering Zeeman APP atomic_parameters()')
        
        configur = ConfigParser()
        configur.read('config.ini')
        self.search_Atom_Ion = self.ui.comboBox_Atom_Ion.currentText()
        
        if self.search_Atom_Ion == '87Sr':
     
            self.zeeman.m = 1.6605e-27 * configur.getfloat('atomic_parameter_Sr87','m') #[Kg]
            self.zeeman.WL_ge = configur.getfloat('atomic_parameter_Sr87','WL_ge') 
            self.zeeman.gamma = configur.getfloat('atomic_parameter_Sr87','gamma')
            self.zeeman.mu_eff = 9.274e-24 * configur.getfloat('atomic_parameter_Sr87','mu_eff') #[J/T]

        elif self.search_Atom_Ion == '171Yb':

            self.zeeman.m = 1.6605e-27 * configur.getfloat('atomic_parameter_Yb171','m') #[Kg]
            self.zeeman.WL_ge = configur.getfloat('atomic_parameter_Yb171','WL_ge') 
            self.zeeman.gamma = configur.getfloat('atomic_parameter_Yb171','gamma') 
            self.zeeman.mu_eff = 9.274e-24 * configur.getfloat('atomic_parameter_Yb171','mu_eff') #[J/T]
 
        self.ui.pushButton_Find_2.hide()
        self.ui.pushButton_2D_magnetic_field.hide()
        self.ui.pushButton_atomic_kinetics.hide()
        self.ui.pushButton_save_file.hide()
        
        if self.test==True:  print('<<--EXITING Zeeman APP atomic_parameters()')
            
    def update_GUI(self):
        # We update GUI with present values
        if self.test==True: print('-->> Entering Zeeman APP update_GUI')
        self.blockSignals(True)
        self.ui.lineEdit_Number_of_magnets.setValue((self.zeeman.Npm))
        self.ui.lineEdit_Power_laser.setValue((self.zeeman.P*1000))
        self.ui.lineEdit_ZS.setValue((self.zeeman.LZ*100))
        self.ui.lineEdit_V_cap.setValue((self.zeeman.V_cap))
        self.ui.lineEdit_V_sal.setValue((self.zeeman.V_fin))
        self.ui.lineEdit_d0_Mhz.setValue(((self.zeeman.d0_Mhz)))
        self.ui.lineEdit_w0.setValue((self.zeeman.w0*1000))
        self.ui.lineEdit_mag_D.setValue(self.zeeman.mag_diam)
        self.ui.lineEdit_mag_H.setValue((self.zeeman.mag_heig))
        self.ui.lineEdit_Tmagz.setValue((self.zeeman.Tmagz))
        if self.zeeman.magnets==[[],[]]:
            self.ui.lineEdit_Length_apparatus.setValue(self.zeeman.LZ*100+2*self.zeeman.LZ/(self.zeeman.Npm-2)*100)
        else:
            self.ui.lineEdit_Length_apparatus.setValue(round(0.1*(self.zeeman.magnets[0][-1].position[2]-self.zeeman.magnets[0][0].position[2]),1))
        self.blockSignals(False)
        if self.test==True: print('<<--EXITING Zeeman APP update_GUI')
        
    def create_spinboxes(self): 
        """ 
            Creates list of spinboxes to manage
        """      
        if self.test==True: print('-->> Entering Zeeman APP create_spinboxes()')
        #Empty lists
        self.listSpinbox_movH = []
        self.listSpinbox_movV = []
        self.list_label_magnet = []

        #Add a label, horizontal and vertical spinbox per pair of magnets
        #and hide them. Will be shown for initial position
        for n in range(1,self.npm_max+1):
            exec ("self.listSpinbox_movH.append(self.ui.dSP_H_%s)" % (n))
            exec ("self.ui.dSP_H_%s.hide()" % (n))
            exec ("self.listSpinbox_movV.append(self.ui.dSP_V_%s)" % (n))
            exec ("self.ui.dSP_V_%s.hide()" % (n))
            exec ("self.list_label_magnet.append(self.ui.label_m_%s)" % (n))
            exec ("self.ui.label_m_%s.hide()" % (n))
        
        if self.test==True: print('<<--EXITING Zeeman APP create_spinboxes()')
        
    def position_ini(self):
        """ 
            Set initial position for magnets (close to the tube)
        """
        print (self.test)
        if self.test==True: print('-->> Entering Zeeman APP position_ini()')
        
        self.zeeman.prepare_data()
  
        if self.test==True: print(f"{Fore.YELLOW}In position_ini(), self.error = {self.error}{Style.RESET_ALL}")
        
        if self.error == False:
            if self.test==True: print("\n ->> Magnets starting position") #TEST
    
            #Clear previuous plots in case they exist
            self.pw.ax_B.clear()
            self.pw.ax_B1.clear()
            
            # Calculate B_field, create magnets collection and set initial position
            
            self.zeeman.initial_B_calculation()
            if self.zeeman.zero_cross == None:
                self.error == True
                self.values_error = 'B field does not cross zero. Check detuning, capture and ending speeds'
                self.show_error()
                return
            
            self.zeeman.create_magnets()                 
            self.zeeman.preliminary_position()
            
            self.spinbox_update_flag = True
            
            # Actualiza spinboxs
            self.spinbox_hide()
            self.spinbox_show()
            self.spinbox_update()
            self.spinbox_update_flag = False 
    
            # Automatic calulation of the whole length of apparatus        
            
            aux = self.zeeman.LZ + (self.zeeman.magnets[0][1].position[2]-self.zeeman.magnets[0][0].position[2])/1000 + (self.zeeman.magnets[0][-1].position[2]-self.zeeman.magnets[0][-2].position[2])/1000
            self.ui.lineEdit_Length_apparatus.setValue(aux*100)    
    
            if self.primer == True:
                self.primer = False
                self.listSpinbox_movV[0].valueChanged.connect(lambda x: self.move_V(x,0))
                self.listSpinbox_movV[1].valueChanged.connect(lambda x: self.move_V(x,1))
                self.listSpinbox_movV[2].valueChanged.connect(lambda x: self.move_V(x,2))
                self.listSpinbox_movV[3].valueChanged.connect(lambda x: self.move_V(x,3))
                self.listSpinbox_movV[4].valueChanged.connect(lambda x: self.move_V(x,4))
                self.listSpinbox_movV[5].valueChanged.connect(lambda x: self.move_V(x,5))
                self.listSpinbox_movV[6].valueChanged.connect(lambda x: self.move_V(x,6))
                self.listSpinbox_movV[7].valueChanged.connect(lambda x: self.move_V(x,7))
                self.listSpinbox_movV[8].valueChanged.connect(lambda x: self.move_V(x,8))
                self.listSpinbox_movV[9].valueChanged.connect(lambda x: self.move_V(x,9))
                self.listSpinbox_movV[10].valueChanged.connect(lambda x: self.move_V(x,10))
                self.listSpinbox_movV[11].valueChanged.connect(lambda x: self.move_V(x,11))
                self.listSpinbox_movV[12].valueChanged.connect(lambda x: self.move_V(x,12))
                self.listSpinbox_movV[13].valueChanged.connect(lambda x: self.move_V(x,13))
                self.listSpinbox_movV[14].valueChanged.connect(lambda x: self.move_V(x,14))
                self.listSpinbox_movV[15].valueChanged.connect(lambda x: self.move_V(x,15))
                self.listSpinbox_movV[16].valueChanged.connect(lambda x: self.move_V(x,16))
                self.listSpinbox_movV[17].valueChanged.connect(lambda x: self.move_V(x,17))
                self.listSpinbox_movV[18].valueChanged.connect(lambda x: self.move_V(x,18))
                self.listSpinbox_movV[19].valueChanged.connect(lambda x: self.move_V(x,19))
                self.listSpinbox_movH[0].valueChanged.connect(lambda x: self.move_H(x,0))
                self.listSpinbox_movH[1].valueChanged.connect(lambda x: self.move_H(x,1))
                self.listSpinbox_movH[2].valueChanged.connect(lambda x: self.move_H(x,2))
                self.listSpinbox_movH[3].valueChanged.connect(lambda x: self.move_H(x,3))
                self.listSpinbox_movH[4].valueChanged.connect(lambda x: self.move_H(x,4))
                self.listSpinbox_movH[5].valueChanged.connect(lambda x: self.move_H(x,5))
                self.listSpinbox_movH[6].valueChanged.connect(lambda x: self.move_H(x,6))
                self.listSpinbox_movH[7].valueChanged.connect(lambda x: self.move_H(x,7))
                self.listSpinbox_movH[8].valueChanged.connect(lambda x: self.move_H(x,8))
                self.listSpinbox_movH[9].valueChanged.connect(lambda x: self.move_H(x,9))
                self.listSpinbox_movH[10].valueChanged.connect(lambda x: self.move_H(x,10))
                self.listSpinbox_movH[11].valueChanged.connect(lambda x: self.move_H(x,11))
                self.listSpinbox_movH[12].valueChanged.connect(lambda x: self.move_H(x,12))
                self.listSpinbox_movH[13].valueChanged.connect(lambda x: self.move_H(x,13))
                self.listSpinbox_movH[14].valueChanged.connect(lambda x: self.move_H(x,14))
                self.listSpinbox_movH[15].valueChanged.connect(lambda x: self.move_H(x,15))
                self.listSpinbox_movH[16].valueChanged.connect(lambda x: self.move_H(x,16))
                self.listSpinbox_movH[17].valueChanged.connect(lambda x: self.move_H(x,17))
                self.listSpinbox_movH[18].valueChanged.connect(lambda x: self.move_H(x,18))
                self.listSpinbox_movH[19].valueChanged.connect(lambda x: self.move_H(x,19))
            
            self.ui.pushButton_Find_2.show()
            self.ui.pushButton_2D_magnetic_field.show()
            self.ui.pushButton_atomic_kinetics.show()
            self.ui.pushButton_save_file.show()
            self.ui.pushButton_load_file.show()
            
            self.initial_pos_flag = True
            
            if self.test==True: print('<<--EXITING Zeeman APP position_ini()')

    def load_GUI_data(self): 
        self.ui.centralwidget.setFocus()
        if self.test==True: print('-->> Entering Zeeman APP load_GUI_data()')
        """ 
            Reads data from GUI and updates zeeman object
        """
        if self.test==True: print("\n ->> Load data from the GUI") #TEST 
        #Number of pairs of magnets
        self.zeeman.Npm = int(self.ui.lineEdit_Number_of_magnets.value())
        
        #Laser power read in [mW], stored in [W]
        self.zeeman.P = float(self.ui.lineEdit_Power_laser.value())/1000
        
        #Length of braking distance read in [cm], stored in [m]
        self.zeeman.LZ = float(self.ui.lineEdit_ZS.value())/100
                
        #Capture and final velocities [m/s]
        self.zeeman.V_cap = int(self.ui.lineEdit_V_cap.value())
        self.zeeman.V_fin = int(self.ui.lineEdit_V_sal.value()) 
        
        #Detuning [MHz] and [Mrad/s]
        self.zeeman.d0_Mhz = int(self.ui.lineEdit_d0_Mhz.value())
        self.zeeman.Delta0 = 1e6 * 2 * np.pi * self.zeeman.d0_Mhz
 
        #Beam waist diameter read in [mm], stored in [m]
        self.zeeman.w0 = float(self.ui.lineEdit_w0.value())/1000 

        
        #Cylindric Magnets size [mm]
        self.zeeman.mag_diam = float(self.ui.lineEdit_mag_D.value()) 
        self.zeeman.mag_heig = float(self.ui.lineEdit_mag_H.value())  
        self.zeeman.size_mag = (self.zeeman.mag_diam,self.zeeman.mag_heig)
                
        # Magnets remanescence [mT]
        self.zeeman.Tmagz = int(self.ui.lineEdit_Tmagz.value())

        self.ui.pushButton_Update.hide()
        
        self.check_values() # We check if values are right
    
        if self.test==True: print('<<--EXITING Zeeman APP load_GUI_data()')   
      

    def position_opt(self):
        """ 
        Starts the optimization process in a background thread to keep GUI responsive.
        """
        if self.test: print('-->> Entering Zeeman APP position_opt()')
        if self.test: print("INITIAL POSITION \n") 
        
        # --- PROTECTION 1: Avoid double execution ---
        # If there is a worker running we do nothing
        if hasattr(self, 'worker') and self.worker is not None and self.worker.isRunning():
            print("Optimization is already running. Ignoring request.")
            return

        # --- PROTECTION 2: Cleaning up old connections ---
        # We disconnect previous signal of cancel button
        try:
            self.loading_screen.cancel_signal.disconnect()
        except TypeError:
            pass # Ignore if no connection
        
        self.was_cancelled = False
        
        # 1. Initialize Loading Screen
        self.loading_screen.show_loading("Optimizing magnets... This may take about 2 minutes.\nCheck console for progress.", without_button=False)
        self.loading_screen.update_progress(0)
        
        try:
            # 2. Configure Worker Thread
            # We pass the MASTER function from ZeemanCore (optimal_position)
            self.worker = WorkerThread(self.zeeman.optimal_position)
            
            # 3. Connect Signals (Worker -> GUI)
            self.worker.progress_signal.connect(self.loading_screen.update_progress)
            self.worker.finished_signal.connect(self.on_optimization_finished)
            self.worker.error_signal.connect(self.on_optimization_error)
            
            # 4. Connect Cancel Button
            # Connect the loading screen cancel signal to our stop function
            self.loading_screen.cancel_signal.connect(self.stop_optimization)

            # 5. Start the Thread
            self.worker.start()
                                
        except Exception as e:
            print(f"{Fore.RED} Thread setup error: {e}")
            self.loading_screen.stop_loading()
        
        if self.test: print('<<-- EXITED Zeeman APP position_opt() (Thread running in background)')

    def stop_optimization(self):
        """
        Sets the flag in ZeemanCore to break the calculation loops.
        """
        print("Stopping optimization requested...")
        self.zeeman.break_simulations = True
        self.was_cancelled = True
        

    def on_optimization_finished(self):
        """
        Called when the optimization thread completes successfully.
        Updates the GUI and plots.
        """
        self.loading_screen.stop_loading()
        
        # 1. Update Spinboxes with new magnet positions
        self.spinbox_update_flag = True
        self.spinbox_update()
        self.spinbox_update_flag = False
        
        # 2. Refresh Graphics
        # Recalculate B field with final positions just in case
        self.update_needed_B() 
        
        # Clear and redraw axes
        self.pw.ax_B.clear()
        self.pw.ax_B1.clear()
        # Redraw structure
        self.zeeman.initial_plot(1000*self.zeeman.z, self.zeeman.By_ideal_full, self.zeeman.By_current_full)
        
        self.pw.draw()
        
        if self.was_cancelled:
            # A. If it was cancelled
            QMessageBox.warning(self, "Cancelled", "Optimization process stopped by user.\nResults show the state at the moment of interruption.")
            
            # Important: Ensure the core flag is reset for next time
            self.zeeman.break_simulations = False 
            
        else:
            # B. If it finished naturally
            QMessageBox.information(self, "Optimization Finished", "Magnet configuration optimized successfully.")

    def on_optimization_error(self, error_msg):
        """
        Called if the worker thread crashes.
        """
        self.loading_screen.stop_loading()
        print(f"{Fore.RED} Optimization Error: {error_msg}")
        QMessageBox.critical(self, "Optimization Error", f"An error occurred during calculation:\n{error_msg}")
               
    def generate_2Dplot(self):
        """ 
        Generation of a new window including not only active magnets and B_field profile
        but also initial and final magnet and B_field 2D lines in a transversal plane X=0 (YZ)
        """
        if self.test==True: print('-->> Entering Zeeman APP generate_2Dplot()')
        
        self.loading_screen.show_loading("Preparing requested graphics... This may take about 10-20 seconds depending on your system.",without_button=True)
        
        try:
          self.zeeman.B_field_2D_lines_drawing() 
        except Exception as e:
            print(f"{Fore.RED} Error generating graphics: {e}")        
        finally:
            self.loading_screen.stop_loading()
        
        
        if self.test==True: print('<<--EXITING Zeeman APP generate_2Dplot()')
        
 
    def run_atomic_kinetics(self):
        """ 
        Starts the atomic kinetics calculation in a background thread.
        Replaces the old synchronous 'atomic_kinetics' function.
        """
        if self.test: print('-->> Entering Zeeman APP run_atomic_kinetics()')

        # --- 1. PRE-CHECKS: Avoid double execution ---
        if hasattr(self, 'worker') and self.worker is not None and self.worker.isRunning():
            print("Kinetics process is already running.")
            return

        # --- 2. CLEANUP: Disconnect previous cancel signals ---
        try:
            self.loading_screen.cancel_signal.disconnect()
        except TypeError:
            pass # Ignore if not connected

        # --- 3. RESET FLAGS ---
        self.was_cancelled = False
        self.zeeman.break_simulations = False 
        
        # --- 4. UI SETUP ---
        self.loading_screen.show_loading("Calculating Atomic Kinetics...\nSolving differential equations.", without_button=False)
        self.loading_screen.update_progress(0)
        
        try:
            # --- 5. THREAD CONFIGURATION ---
            # We pass the Core function 'atomic_kinetics' to the worker
            self.worker = WorkerThread(self.zeeman.atomic_kinetics)
            
            # Connect Signals
            self.worker.progress_signal.connect(self.loading_screen.update_progress)
            self.worker.finished_signal.connect(self.on_kinetics_finished)
            self.worker.error_signal.connect(self.on_kinetics_error)
            
            # Connect Cancel Button
            self.loading_screen.cancel_signal.connect(self.stop_kinetics)

            # --- 6. START ---
            self.worker.start()
                     
        except Exception as e:
            print(f"{Fore.RED} Thread setup error: {e}")
            self.loading_screen.stop_loading()
            
        if self.test: print('<<-- EXITED Zeeman APP run_atomic_kinetics() (Thread running in background)')

    def stop_kinetics(self):
        """
        Triggered when the user clicks 'Stop Calculation' on the loading screen.
        """
        print("Stopping kinetics requested...")
        self.was_cancelled = True
        self.zeeman.break_simulations = True

    def on_kinetics_finished(self):
        """
        Called when the calculation thread ends.
        """
        self.loading_screen.stop_loading()
        
        if self.was_cancelled:
            QMessageBox.warning(self, "Cancelled", "Atomic kinetics simulation stopped by user.")
            # Reset flag for future runs
            self.zeeman.break_simulations = False 
        else:
            # If the figure was created in Core but not shown:
            try:
                self.zeeman.plot_atomic_kinetics()
            except Exception as e:
                print(f"Error showing plots: {e}")

            QMessageBox.information(self, "Finished", "Atomic kinetics calculation completed.")

    def on_kinetics_error(self, error_msg):
        """
        Called if the worker thread crashes.
        """
        self.loading_screen.stop_loading()
        print(f"{Fore.RED} Kinetics Error: {error_msg}")
        QMessageBox.critical(self, "Error", f"An error occurred in kinetics:\n{error_msg}")


    def file_generate(self):
        """ 
        Save in a data file main values used in simulation: Atom/Ion, magnets positions, etc.
        """

        if self.test==True: print('-->> Entering Zeeman APP file_generate()')
        
        self.loading_screen.show_loading("Saving data file...\nThis may take a while.\n",without_button=True)
        
        parent_dir=os.getcwd()
        
        try:
            # Folder creation
            timestamp = dtm.now().strftime("%Y%m%d")
            folder_name = f"{timestamp}_SavedData"
            save_path = os.path.join(parent_dir, folder_name)
            os.makedirs(save_path, exist_ok=True)
            
            # Data savings
            timestamp = dtm.now().strftime("%H_%M_%S")
            h5_filename = os.path.join(save_path, f"{timestamp}_simulation_data.h5")
            
            if self.test==True: print("FILE GENERATED \n") #TEST 
            
            # Writes down the main attributes of zeeman object
            with h5py.File(h5_filename, 'w') as f:
                # --- Metadata ---
                f.attrs['Date'] = dtm.now().isoformat()
                f.attrs['Description'] = 'Zeeman Slower Simulation Data'
                                
                # --- GROUP: PHYSICAL PARAMETERS ---
                grp_params = f.create_group("Simulation_Parameters")
                
                grp_params.attrs['Atom_Species'] = self.ui.comboBox_Atom_Ion.currentText()
                # =================================================================
                # MASTER DICTIONARY OF VARIABLES AND UNITS
                # =================================================================
                units_map = {
                    # --- Design and Geometry Parameters ---
                    'LZ':               'm',    # Slower Length
                    'Npm':              '#',    # Number of Magnets
                    'mag_diam':         'mm',    # Diameter (Assuming SI, change to 'mm' if saving in mm)
                    'mag_heig':         'mm',    # Height
                    'Tmagz':            'mT',    # Spatial Period Z
                    'ext_tube_radius':  'mm',   # External Tube Radius
                    'displ':            'mm',    # Displacement
                    'sep_ini':          'mm',    # Initial Separation
                    'sep_last':         'mm',    # Final Separation
                    'zero_cross':       '#',    # Zero-crossing Index
                    'min_magnet_distance': 'mm',# Minimum Magnet Distance

                    # --- Velocities and Capture Configuration ---
                    'V_cap':            'm/s',  # Capture Velocity
                    'V_fin':            'm/s',  # Final Velocity
                    'use_sigma_plus':   'bool', # Boolean
                    'eta':              'adim', # Design Parameter (0-1)
                    
                    # --- Laser ---
                    'P':                'W',    # Power
                    'w0':               'm',    # Beam Waist
                    'd0_Mhz':           'MHz',  # Detuning (based on variable name)
                    'k0':               '1/m',  # Wavenumber
                    'WL_ge':            'm',    # Wavelength
                    'I_sat':            'W/m2', # Saturation Intensity
                    'I_max':            'W/m2', # Maximum Intensity
                    's_max':            'adim', # Saturation Parameter
                    # 'rabi_omega0':      'rad/s',# Rabi Frequency

                    # --- Atomic Physics and Constants ---
                    'm':                'kg',   # Atomic Mass
                    'mu_eff':           'adim',  # Effective Magnetic Moment
                    'gamma0':           'Hz',   # Natural Linewidth

                    # --- Time Simulation ---
                    'dt':               's',    # Time Step
                    'Nt':               '#',    # Number of Steps
                    'N_vel':            '#',    # Number of Velocity Groups
                    'atoms_initial_z_position': 'mm', 
                    'scale_factor_B':  'adim'
                    
                }

                for var_name, unit in units_map.items():
                    # 1. We get real variable name
                    val = getattr(self.zeeman, var_name, "N/A")
                    
                    # 2. Cleaning numpy types
                    if hasattr(val, 'item'): val = val.item()
                    
                    attr_name = f"{var_name}[{unit}]"
                    
                    try:
                        # 3. We save as simple attribute
                        grp_params.attrs[attr_name] = val

                        
                    except Exception as e:
                        print(f"Error saving parameter {attr_name}: {e}")
                        # Fallback: if fails creating dataset (i.e. it's string), we save as simple attribute
                        grp_params.attrs[attr_name] = str(val)
                       
                
                # --- Magnets ---

                grp_mag = f.create_group("Magnets_Config")
                if hasattr(self.zeeman, 'magnets') and len(self.zeeman.magnets) > 0:
                    
                    # We look every set of magnets (i.e.: 0=up, 1=down)
                    for set_index, magnet_list in enumerate(self.zeeman.magnets):
                        
                        positions = []
                        for mag in magnet_list:
                            positions.append(mag.position)
                        
                        # We create a dataset for each: 
                        # positions_set_0[mm], positions_set_1[mm]
                        dset_name = f"positions_set_{set_index}[mm]"
                        grp_mag.create_dataset(dset_name, data=np.array(positions))
                
                # --- Field profiles ---
                grp_field = f.create_group("Field_Profiles")
                if hasattr(self.zeeman, 'z_axis_full'):
                    grp_field.create_dataset("z_axis[mm]", data=1000*self.zeeman.z_axis_full)
                    grp_field.create_dataset("By_current[mT]", data=self.zeeman.By_current_full)
                    grp_field.create_dataset("By_ideal[mT]", data=self.zeeman.By_ideal_full)
                
                # --- Atoms kinetics (Si existe) ---
                grp_kin = f.create_group("Atomic_Kinetics")
                if hasattr(self.zeeman, 'Atoms_position'):
                    if self.zeeman.Atoms_speed.ndim == 2:
                        grp_kin.create_dataset("Atoms positions z[mm]", data=1000*self.zeeman.Atoms_position,compression='gzip')
                        grp_kin.create_dataset("Atom velocities z[m·s-1]", data=self.zeeman.Atoms_speed,compression='gzip')
                    elif self.zeeman.Atoms_speed.ndim == 3:
                        grp_kin.create_dataset("Atoms positions z[mm]", data=1000*self.zeeman.Atoms_position[:,:,2],compression='gzip')
                        grp_kin.create_dataset("Atom velocities z[m·s-1]", data=self.zeeman.Atoms_speed[:,:,2],compression='gzip')
                    else: 
                        pass
                
            # ---------------------------------------------------------
            # PART B: SAVE GRAPHICS (PNG)
            # ---------------------------------------------------------
            # Dictionary of posible figures to save {Name: Object}
            
            figures_to_save = {
                "Graph_2D_MagneticField": getattr(self.zeeman, 'fig_2D', None),
                "Graph_Atomic_Kinetics": getattr(self.zeeman, 'fig_vels', None), 
            }
            
            saved_figs_count = 0
            
            for name, fig in figures_to_save.items():
                # Verificamos si la figura existe y es válida
                if fig is not None:
                    try:
                        file_path = os.path.join(save_path, f"{timestamp}_{name}.png")
                        
                        fig.savefig(file_path, dpi=300, bbox_inches='tight')
                        saved_figs_count += 1
                    except Exception as e_fig:
                        print(f"Couldn't save figure {name}: {e_fig}")
                else:
                    
                    print(f"WARNING: Figure '{name}' is None (optimization, atomic kinetics or 2D_B_field lines not generated or closed).")
            # Feedback final
            msg = f"Save succeeded in:\n{folder_name}\n\n- File HDF5 created.\n- {saved_figs_count} Graphics exported."
            QMessageBox.information(self, "Done saving", msg)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed saving:\n{e}")
            print(f"Detailed data: {e}")
            
        finally:
            self.loading_screen.stop_loading()
                        
        if self.test==True: print('<<--EXITING Zeeman APP file_generate()')
  
    def move_V(self,move_distance,pair_number):
        """ 
            Moves in vertical direction (y) pairs of magnets "pair_number" a certain distance "distance"
        """
        if self.test==True: print('-->> Entering Zeeman APP move_V()')
        aux=0
        
        if self.spinbox_update_flag == False:
            #print ("move V")
            if pair_number >= self.zeeman.zero_cross+1:
                aux = 1
            else:
                aux=0
            
            if move_distance < self.zeeman.min_magnet_distance:
                self.spinbox_update()  
                self.values_error = 'Cannot aproximate the magnet closer to the tube'
                self.show_error()              
                return
            
            total_distance = move_distance - self.zeeman.magnets[0][pair_number+aux].position[1]

            self.zeeman.move_magnet_V(pair_number+aux,total_distance)
        
        
        
        if self.test==True: print('<<--EXITING Zeeman APP move_V()')

    def move_H(self,move_distance,pair_number):
        """ 
        Moves in horizontal direction (z) pairs of magnets "pair_number" a certain distance "distance"
        """
        if self.test==True: print('-->> Entering Zeeman APP move_H()')
        
        error_moving_V = False
        print('Pair number', pair_number,'--- Zero Cross',self.zeeman.zero_cross)
        
        if pair_number >= self.zeeman.zero_cross+1:
            aux = 1
        else:
            aux=0
        
        if self.spinbox_update_flag == False:

            if pair_number == 0:
                if np.abs(move_distance - self.zeeman.magnets[0][pair_number+1].position[2]) < self.zeeman.mag_diam:
                    print(move_distance - self.zeeman.magnets[0][pair_number+1].position[2])
                    self.spinbox_update()  
                    error_moving_V = True
            elif pair_number == self.zeeman.Npm-1:
                print(self.zeeman.Npm-1)
                if np.abs(move_distance - self.zeeman.magnets[0][pair_number].position[2]) < self.zeeman.mag_diam:
                    print(move_distance - self.zeeman.magnets[0][pair_number].position[2])
                    self.spinbox_update()  
                    error_moving_V = True
            elif pair_number == self.zeeman.zero_cross + 1:
               if np.abs(move_distance - self.zeeman.magnets[0][pair_number+2].position[2]) < self.zeeman.mag_diam:
                   print(move_distance - self.zeeman.magnets[0][pair_number+2].position[2])
                   self.spinbox_update()  
                   error_moving_V = True
               elif np.abs(move_distance - self.zeeman.magnets[0][pair_number-1].position[2]) < self.zeeman.mag_diam:
                   print(move_distance - self.zeeman.magnets[0][pair_number-1].position[2])
                   self.spinbox_update()  
                   error_moving_V = True
            elif pair_number == self.zeeman.zero_cross:
               if np.abs(move_distance - self.zeeman.magnets[0][pair_number-1].position[2]) < self.zeeman.mag_diam:
                   print(move_distance - self.zeeman.magnets[0][pair_number-1].position[2])
                   self.spinbox_update()  
                   error_moving_V = True
               elif np.abs(move_distance - self.zeeman.magnets[0][pair_number+2].position[2]) < self.zeeman.mag_diam:
                   print(move_distance - self.zeeman.magnets[0][pair_number+2].position[2])
                   self.spinbox_update()  
                   error_moving_V = True
            else:
                if (np.abs(move_distance - self.zeeman.magnets[0][pair_number+aux-1].position[2]) < self.zeeman.mag_diam) or (np.abs(move_distance - self.zeeman.magnets[0][pair_number+aux+1].position[2]) < self.zeeman.mag_diam):
                    print(move_distance - self.zeeman.magnets[0][pair_number+aux-1].position[2])
                    print(move_distance - self.zeeman.magnets[0][pair_number+1].position[2])                                                                                                  
                    self.spinbox_update()  
                    error_moving_V = True
            
            if error_moving_V == True:
                self.values_error = 'Cannot aproximate magnets so close to the next one'
                self.error = True
                self.show_error()
                return
                   

      
            total_distance = move_distance - self.zeeman.magnets[0][pair_number+aux].position[2]
            print(f"{Fore.CYAN} Move H TOTAL DISTANCE = {total_distance}{Style.RESET_ALL}")
            print(f"{Fore.CYAN} Move H MOVE DISTANCE = {move_distance}{Style.RESET_ALL}")
            print(f"{Fore.CYAN} Move H MAGNET POSITION = {self.zeeman.magnets[0][pair_number+aux].position[2]}{Style.RESET_ALL}")
    
            self.zeeman.move_magnet_H(pair_number+aux,total_distance)  
            
            if pair_number==0 or pair_number==self.zeeman.Npm-1:
                self.blockSignals(True) 
                self.ui.lineEdit_Length_apparatus.setValue(round(0.1*(self.zeeman.magnets[0][-1].position[2]-self.zeeman.magnets[0][0].position[2]),1))
                self.blockSignals(False) 
        
        if self.test==True: print('<<--EXITING Zeeman APP move_H()')
            
    def spinbox_hide(self):
        """ 
            Hides unused spinboxes.
        """
        
        if self.test==True: print('-->> Entering Zeeman APP spinbox_hide()')

        for n in range(self.zeeman.Npm+1,self.npm_max+1):
            exec ("self.ui.dSP_H_%s.hide()" % (n))
            exec ("self.ui.dSP_V_%s.hide()" % (n))
            exec ("self.ui.label_m_%s.hide()" % (n))
        
        if self.test==True: print('<<--EXITING Zeeman APP spinbox_hide()')
        
    def spinbox_show(self):
        """ 
            Show spinboxes of present pairs of magnets.
        """
        if self.test==True: print('-->> Entering Zeeman APP spinbox_show()')
        aux = 0

        for n in range(1,self.zeeman.Npm+1):
            print(self.npm_max, self.zeeman.Npm)         
            if n > self.npm_max:
                pass
            else:
                exec ("self.ui.dSP_H_%s.show()" % (n))
                exec ("self.ui.dSP_V_%s.show()" % (n))
                exec ("self.ui.label_m_%s.show()" % (n))
                exec ("self.ui.label_m_%s.setText('%s')" % (n,n-aux))

        if self.test==True:  print('<<--EXITING Zeeman APP spinbox_show()')
        
    def spinbox_update(self):
        """ 
            Updates spinboxes values when  magnets position optimization is running
        """
        for i in range(len(self.listSpinbox_movH)):
            self.listSpinbox_movH[i].blockSignals(True)
            self.listSpinbox_movV[i].blockSignals(True)
            
        if self.test==True: print('-->> Entering Zeeman APP spinbox_update()')
        aux=0
        for n in range(0,self.zeeman.Npm):
            if n >= self.npm_max:
                pass
            #Case of void magnet (Bfield crossing zero)
            elif n==(self.zeeman.zero_cross+1):
                aux = 1 
                self.listSpinbox_movH[n].setValue(int(self.zeeman.magnets[0][n+aux].position[2]))
                self.listSpinbox_movV[n].setValue(int(self.zeeman.magnets[0][n+aux].position[1]))    
            #Rest of cases
            else:
                if n==self.zeeman.Npm:
                    aux=0   #Last magnet moves with previous one
                self.listSpinbox_movH[n].setValue(int(self.zeeman.magnets[0][n+aux].position[2]))
                self.listSpinbox_movV[n].setValue(int(self.zeeman.magnets[0][n+aux].position[1])) 
        
        for i in range(len(self.listSpinbox_movH)):
            self.listSpinbox_movH[i].blockSignals(False)
            self.listSpinbox_movV[i].blockSignals(False)

        if self.test==True: print('<<--EXITING Zeeman APP spinbox_update()')

    
    def update_needed_B(self):
        """ 
            Update B when data in GUI is modified
        """
        if self.test==True: print('-->> Entering Zeeman APP update_needed_B')
        
        
        print (f"{Fore.YELLOW}Initial pos flag = {self.initial_pos_flag}{Style.RESET_ALL}")
        if self.initial_pos_flag == True:
            self.zeeman.current_B()
            self.zeeman.plot_data()
        else:
            pass
        
        if self.test==True: print('<<--EXITING Zeeman APP update_needed_B')
    

    def load_data_from_file(self):
        """
        Loads configuration data from an HDF5 file and updates the App.
        Includes Atom loading and dynamic SpinBox visibility update.
        """
        if self.test: print('-->> Entering Zeeman APP load_data_from_file()')
        self.blockSignals(True)
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(
            self, "Load Data File", os.getcwd(), "HDF5 Files (*.h5);;All Files (*)", options=options
        )

        if not fileName: return 

        self.loading_screen.show_loading("Loading data...", without_button=False)

        try:
            with h5py.File(fileName, 'r') as f:
                
                # --- STEP 1: LOAD SCALARS ---
                if "Simulation_Parameters" in f:
                    grp_params = f["Simulation_Parameters"]
                    
                    # 1.1 Load basic attributes
                    for key, val in grp_params.attrs.items():
                        var_name = key.split('[')[0] 
                        if var_name != 'Atom_Species' and hasattr(self.zeeman, var_name):
                            setattr(self.zeeman, var_name, val)
                    
                    # 1.2 LOAD ATOM / ION SPECIES
                    if 'Atom_Species' in grp_params.attrs:
                        atom_name = grp_params.attrs['Atom_Species']
                        # Look up in combo box
                        index = self.ui.comboBox_Atom_Ion.findText(atom_name)
                        if index >= 0:
                            self.ui.comboBox_Atom_Ion.setCurrentIndex(index)
                            # Important: update atoms physics(mass, lambda...)
                            self.atomic_parameters() 
                            print(f"Atom loaded: {atom_name}")

                # 1.3 Specific Dimensions
                if 'mag_diam' in f: self.zeeman.mag_diam = float(f['mag_diam'][()])
                if 'mag_heig' in f: self.zeeman.mag_heig = float(f['mag_heig'][()])
                if 'Tmagz' in f:    self.zeeman.Tmagz = float(f['Tmagz'][()])
                if 'ext_tube_radius' in f: self.zeeman.ext_tube_radius = float(f['ext_tube_radius'][()])

                self.zeeman.size_mag = (self.zeeman.mag_diam, self.zeeman.mag_heig)

                # --- STEP 2: RECALCULATE PHYSICS ---
                self.zeeman.prepare_data()          
                self.zeeman.initial_B_calculation() 
                
                # --- STEP 3: CREATE MAGNETS ---
                self.zeeman.create_magnets()
                
                # --- STEP 4: APPLY POSITIONS ---
                if "Magnets_Config" in f:
                    grp_mag = f["Magnets_Config"]
                    for key in grp_mag.keys():
                        if "positions_set_" in key:
                            try:
                                idx_str = key.split('set_')[1].split('[')[0]
                                set_index = int(idx_str)
                                loaded_positions = grp_mag[key][()]
                                if set_index < len(self.zeeman.magnets):
                                    target_list = self.zeeman.magnets[set_index]
                                    limit = min(len(target_list), len(loaded_positions))
                                    for k in range(limit):
                                        target_list[k].position = loaded_positions[k]
                            except Exception: pass

                # --- STEP 5: KINETICS ---
                if "Atomic_Kinetics" in f:
                    grp_kin = f["Atomic_Kinetics"]
                    for key in grp_kin.keys():
                        if "Atoms positions" in key: self.zeeman.Atoms_position = 0.001 * grp_kin[key][()] 
                        if "Atom velocities" in key: self.zeeman.Atoms_speed = grp_kin[key][()]

            # =============================================================
            # UPDATE INTERFACE & VISIBILITY
            # =============================================================
            
            # 1. Update Top-Left Widgets
            self.update_GUI_from_zeeman() 
            
            # 2. DYNAMIC VISIBILITY OF SPINBOXES 
            # We iterate through the lists created in create_spinboxes
            # and show only the ones up to Npm.
            
            current_npm = int(self.zeeman.Npm)
            
            # Aseguramos no pasarnos del máximo de spinboxes creados (npm_max)
            max_spinboxes = len(self.listSpinbox_movH) # Debería ser npm_max
            
            for i in range(max_spinboxes):
                # i va de 0 a 19. Los imanes son 1 a 20.
                if i < current_npm:
                    # Mostrar controles
                    self.listSpinbox_movH[i].show()
                    self.listSpinbox_movV[i].show()
                    self.list_label_magnet[i].show()
                else:
                    # Ocultar controles sobrantes
                    self.listSpinbox_movH[i].hide()
                    self.listSpinbox_movV[i].hide()
                    self.list_label_magnet[i].hide()

            # 3. Update internal values of those spinboxes
            self.spinbox_update() 
            
            # 4. Graphics
            self.pw.ax_B.clear()
            self.pw.ax_B1.clear()
            self.zeeman.initial_plot(1000*self.zeeman.z, self.zeeman.By_ideal, self.zeeman.By_current)
            self.update_needed_B() # Update positions
            self.pw.draw()

            QMessageBox.information(self, "Load Complete", "Data loaded successfully.")

        except Exception as e:
            traceback.print_exc() 
            QMessageBox.critical(self, "Load Error", f"Error: {e}")
        finally:
            self.loading_screen.stop_loading()
            self.ui.pushButton_Find.show()
            self.ui.pushButton_Find.setFocus()
            self.ui.pushButton_Find_2.show()
            self.ui.pushButton_2D_magnetic_field.show()
            self.ui.pushButton_atomic_kinetics.show()
            self.ui.pushButton_save_file.show() 
            self.blockSignals(False)
            if self.test: print('<<-- EXITED Zeeman APP load_data_from_file()')

    

    def update_GUI_from_zeeman(self):
        """
        Vuelca los datos de self.zeeman a los widgets de la interfaz.
        CORREGIDO: Usa los nombres reales (lineEdit_...) detectados en ZeemanGUI.py
        """
        self.blockSignals(True) # Block signals to avoid recalculation loops
        
        try:
            # 1. Number of Magnets (QSpinBox)
            # Nombre en GUI: lineEdit_Number_of_magnets
            if hasattr(self.zeeman, 'Npm') and hasattr(self.ui, 'lineEdit_Number_of_magnets'):
                self.ui.lineEdit_Number_of_magnets.setValue(int(self.zeeman.Npm))

            # 2. Laser Power (QDoubleSpinBox) - W -> mW
            # Nombre en GUI: lineEdit_Power_laser
            if hasattr(self.zeeman, 'P') and hasattr(self.ui, 'lineEdit_Power_laser'):
                self.ui.lineEdit_Power_laser.setValue(self.zeeman.P * 1000)

            # 3. Slower Length (QDoubleSpinBox) - m -> cm 
            # Nombre en GUI: lineEdit_ZS
            if hasattr(self.zeeman, 'LZ') and hasattr(self.ui, 'lineEdit_ZS'):
                self.ui.lineEdit_ZS.setValue(self.zeeman.LZ * 100) 

            # 4. Velocities (QSpinBox/QDoubleSpinBox) - m/s
            # Nombres en GUI: lineEdit_V_cap y lineEdit_V_sal
            if hasattr(self.zeeman, 'V_cap') and hasattr(self.ui, 'lineEdit_V_cap'):
                self.ui.lineEdit_V_cap.setValue(self.zeeman.V_cap)
            
            if hasattr(self.zeeman, 'V_fin') and hasattr(self.ui, 'lineEdit_V_sal'):
                self.ui.lineEdit_V_sal.setValue(self.zeeman.V_fin)

            # 5. Detuning (QDoubleSpinBox) - MHz
            # Nombre en GUI: lineEdit_d0_Mhz
            if hasattr(self.zeeman, 'd0_Mhz') and hasattr(self.ui, 'lineEdit_d0_Mhz'):
                self.ui.lineEdit_d0_Mhz.setValue(self.zeeman.d0_Mhz)

            # 6. Beam Waist (QDoubleSpinBox) - m -> mm
            # Nombre en GUI: lineEdit_w0
            if hasattr(self.zeeman, 'w0') and hasattr(self.ui, 'lineEdit_w0'):
                self.ui.lineEdit_w0.setValue(self.zeeman.w0 * 1000)

            # 7. Magnet Dimensions (QDoubleSpinBox) - m -> mm
            # Nombres en GUI: lineEdit_mag_D, lineEdit_mag_H, lineEdit_Tmagz
            
            if hasattr(self.zeeman, 'mag_diam') and hasattr(self.ui, 'lineEdit_mag_D'):
                self.ui.lineEdit_mag_D.setValue(self.zeeman.mag_diam)
                
            if hasattr(self.zeeman, 'mag_heig') and hasattr(self.ui, 'lineEdit_mag_H'):
                self.ui.lineEdit_mag_H.setValue(self.zeeman.mag_heig)
                
            if hasattr(self.zeeman, 'Tmagz') and hasattr(self.ui, 'lineEdit_Tmagz'):
                self.ui.lineEdit_Tmagz.setValue(self.zeeman.Tmagz) # Tmagz suele ser entero o float directo en mT

            # 8. Aparatus Length (Cálculo derivado)
            # Nombre en GUI: lineEdit_Length_apparatus
            if hasattr(self.ui, 'lineEdit_Length_apparatus'):
                
                total_len = self.zeeman.magnets[0][-1].position[2]-self.zeeman.magnets[0][0].position[2]
                self.ui.lineEdit_Length_apparatus.setValue(round(total_len/10,1))

            if self.test: print("GUI updated successfully with correct widget names.")

        except Exception as e:
            print(f"Error updating GUI widgets: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.blockSignals(False)
        
if __name__ == '__main__':

    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
     
    app.lastWindowClosed.connect(app.exit)
    mainWin = app_gui()
    mainWin.show()
    sys.exit(app.exec_())