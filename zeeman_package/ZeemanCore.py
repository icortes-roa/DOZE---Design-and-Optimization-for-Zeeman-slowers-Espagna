# -*- coding: utf-8 -*-
"""
Created on Fri May 26 09:46:39 2023

@author: elcortex/aestarellas/jcafranga/jromero

# TOCK5 changes QLineEdit -> QSpinBox/QDoubleSpinBox
# TOCK6 Cleaning magnets optimization functions and objects

"""

import magpylib as magpy
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Verdana', 'sans-serif']

from scipy.spatial.transform import Rotation as R
import sympy as sym
import sys
import matplotlib.patches as patches

from datetime import datetime as dtm

from PyQt5.QtWidgets import QApplication


# =============================================================================
'PHYSICS CONSTANT'
# =============================================================================from scipy.constants import c #velocidad de la luz
from scipy.constants import hbar    #Reduced Planck constant h/(2*PI)
from scipy.constants import k as kb #Bolztmann constant
from scipy.constants import pi      #PI
from scipy.constants import e       #Electron charge
from scipy.constants import m_e     #Electron_mass
from scipy.constants import m_p     #Proton mass
from scipy.constants import c       #Speed of light in vacuum


class ZeemanCore(object):
    
    def __init__(self):
        """ 
            Default values for Zeeman object . Will be rewritten with info contained in config.ini and/or GUI.
        """
        print ('-->>Entering ZeemanCore __init__')
        # Variables in order loaded from GUI and config.ini
        self.Npm = 12       # Number of pairs of magnets
        self.P = 70e-3             #Laser power [W]
        self.use_sigma_plus=False  #Consider usage of sigma plus light
        self.eta=0.75              #Eta parameter for usage of full s_max
        self.LZ = 0.25              # Braking length for optimal B_field design [m]
        
        self.V_cap = 400           #Capture velocity [m/s]
        self.V_fin= 40         #Atoms velocity at the end of the slower [m/s]

        self.w0 = 7e-3             #Minimun beam waist Hay que medir [m]

        self.d0_Mhz = - 520        #Default detuning [MHz]
        self.Delta0 = self.d0_Mhz*2*pi*1e6   #Detuning [rad/s]

        self.mag_diam = 30          # Magnets diameter (cylinder) [mm]
        self.mag_heig = 20          # Magnets height [mm]
        self.size_mag = (self.mag_diam,self.mag_heig)     # Magnets size vector as requested by magpylib [mm]

        self.Tmagz = 1300           # Magnet remanescense [mT]
        self.Tmagz_neg = -1300  # Magnet remanescense [mT]
        self.Tmag = (0,0,self.Tmagz)  # Full magnetization vector as requested by magpylib
        self.Tmag_neg = (0,0,self.Tmagz_neg)  # Full magnetization vector as requested by magpylib

        self.ext_tube_radius = 12.0       # External vacuum tube radius [mm]
        self.safety_margin = 6.0        # Additional distance to add (safety distance including magnets support structure) [mm]
        
        
        self.displ=0.1  # Minimum vertical or horizontal magnet movement [mm] (3D printer or manufacturing method resolution)
        self.sep_ini=3  # Fixed y distance betweeen magnet 0 and 1 [mm] (slope adaptation at beginning of the slower)
        self.sep_last=3 # Fixed y distance betweeen last magnet and previous one [mm] (exit speed selection)
        
        self.Nt = 5e3  # Number of time steps for atoms kinetics simulation [a.u.]
        self.dt = 1e-6 # Time step resolution for atoms kinetics simulation [s]
        self.atoms_initial_z_position = -75  # z position where atoms are placed at t=0 of simulation time [mm]

        self.m = 87.62*1.66e-27         # Atom mass [kg] (initialized: Strontium-87)
        self.WL_ge = 4.6086212862e-07   # Atom transition wavelength [m] (typically 1S0-1P1 blue Doppler cooling)
        
        self.gamma0 = 30.24e6           # Atom transition linewiddth [Hz]
        self.GAMMA0 = 2*pi*self.gamma0  # Atom transition wavelength decay rate (1/tau) [rad·Hz]
        self.mu_eff = -0.9994071129074684  #Rate mu_eff/mu_B (Bohr magneton) [a.u]
        
        '''Other variables needed for zeeman class'''
        # Magnets #
        self.magnets = [[],[]]      # Prepare a list for magnet collection
        self.col = None             # Prepare a collection to host magnets
        self.zero_cross = 0         # z_distance where B_field crosses zero
        
        # Number of points for B calculations
        self.B_points=1001
        self.B_points_additional=200
        self.B_points_full=self.B_points+2*self.B_points_additional
        
        # B field scale factor
        self.scale_factor_B = 1.05 #Factor to reduce the B field slope avoiding excessive B field outside deceleration zone stops atoms further than desired
        
        # Variables for z axis vector and ideal B_field y1 and real B_field y2.
        self.By_ideal = np.zeros(self.B_points)         # Ideal By field within LZ
        self.By_current = np.zeros(self.B_points)       # Current By field within LZ
        self.By_ideal_short = None                      # Short B_field to calculate zero crossing
        self.By_ideal_full = np.zeros(self.B_points_full)     # Ideal By field within full apparatus length
        self.By_current_full = np.zeros(self.B_points_full)   # Current By field within full apparatus length
        
        # Magnet max & min position in both axis for plots autoscaling (initializarion)
        self.y_min,self.y_max,self.y_salto = None, None, None
        self.z_min,self.z_max,self.z_salto = None, None, None
        
        # Subplot for By_field, magnets and canvas plot and figure
        self.ax_B = None
        self.ax_magnets = None
        self.canvas_plot = None
        self.fig_plot = None
        
        self.magnet_lines_ax_B={}
        self.magnet_spans_ax_B={}
        
        self.magnet_lines_ax_magnets={}
        self.magnet_spans_ax_magnets={}
        
        self.break_simulations = False
        
        self.iterations_max=50
        
        self.test = False                
        print('<<-- FINISHED Zeeman Core __init__()')
        
    def prepare_data (self):
        '''Other variables needed defined from those in __init__'''
        if self.test==True:print('-->>Entering Zeeman Core prepare_data')
        self.min_magnet_distance = self.ext_tube_radius + self.safety_margin + self.mag_heig/2 # Minimum distance a magnet can be to the atomic axis
        self.safety_distance = self.ext_tube_radius + self.safety_margin
               
        # Wavenumber, Intensities, s parameter 
        self.k0 = 2*pi/self.WL_ge       # 1S0-1P1 Transition Wave number [rad/m]
        self.I_sat = (hbar*c*self.k0**3*self.GAMMA0)/(pi*12) #Saturation intensity of 1S0-1P1 transition
        self.I_max = (2*self.P/(pi*self.w0**2))  # Max laser intensity (W)       
        self.s_max=self.eta*self.I_max/self.I_sat       # s=eta*Imax/Isat [a.u]
        
        # Number of points for B calculations
        self.B_points_full=self.B_points+2*self.B_points_additional
        
        # Variables for z axis vector and ideal B_field y1 and real B_field y2.
        self.z = np.linspace(0,self.LZ,self.B_points)   # 1 dimension atomic axis (z) within LZ [m]
        self.z_axis = np.zeros((self.B_points,3))       # 2 dimensional atomic axis (z) within LZ (initialization)
        self.z_axis[:,2] = self.z                       # 2 dimensional atomic axis (z) within LZ (creation) [m]
        
        # We create a z_axis for the braking length
        self.z_full = np.linspace(-self.B_points_additional*self.LZ/self.B_points,
                                  self.LZ+ self.B_points_additional*self.LZ/self.B_points,
                                  self.B_points_full) # 1 dimension atomic axis (z) within full apparatus length
        self.z_axis_full = np.zeros((self.B_points_full,3))   # 3 dimensional atomic axis (z) within full apparatus length (initialization)
        self.z_axis_full[:,2] = self.z_full              # 3 dimensional atomic axis (z) within full apparatus length (creation) [m]

        
        # Magnets position within braking length [m]
        self.positions = 1000*np.linspace(0,self.LZ,self.Npm-2+1)      # Magnets positions [mm]
        self.By_ideal_short = np.linspace(0,self.LZ,self.Npm-2+1)      # Short B_field to calculate zero crossing (initialization)
        
        if self.test==True:print('<<-- FINISHED Zeeman Core prepare_data()')

    def create_subplots(self,ax_1,ax_2,canvas):
        """ 
            Receive from Zeeman APP the names of axis, canvas and fig
        """
        if self.test==True:print('-->>Entering Zeeman Core create_subplots()')
        self.ax_B = ax_1
        self.ax_magnets = ax_2
        self.canvas_plot = canvas
        self.fig_plot = self.canvas_plot.fig
        if self.test==True: print('<<-- FINISHED Zeeman Core create_subplots()')
            
    
      
    def initial_B_calculation(self):
        ''' Makes the first B calculation, creates a shorter vector for B_field and 
            calculates zero_cross magnet
        '''
        if self.test==True: print('-->>Entering Zeeman Core initial_B_calculation()')
        
        self.calculate_needed_B()
        self.positions = 1000*np.linspace(0,self.LZ,self.Npm-2+1)      # Magnets positions [mm]        
        
        # We use the shortened ideal B (By_ideal_short) where we only have the 
        # values at the z position where the magnets are located
        for i in range(len(self.positions)):
            
            self.By_ideal_short[i]=self.By_ideal[int(i*(1000/(len(self.positions)-1)))]
        
        # We calculate the position where B crosses zero
        self.B_zero_crossing()
    
        if self.test==True: print('<<-- FINISHED Zeeman Core initial_B_calculation()')
        
    def calculate_needed_B(self):
        """ 
            This function calculates magnetic field needed to compensate the Doppler effect
            within the desired distance with the defined detuning, velocities, laser power...
            
        """   
        if self.test==True: print('-->>Entering Zeeman Core calculate_needed_B')
        'Doppler effect calculation'
        #Calculation of decceleration needed. 
        # Factor scale_factor_B=1.05 (default) is to compensate for excessive B_field outside the ideal one at the beginning and end of ideal field
        needed_a=-0.5*(self.V_cap**2-self.V_fin**2)/(self.LZ*self.scale_factor_B)
              
        'Creating an axis to calculate velocities at each point'
        
        V_z=(self.V_cap**2+2*needed_a*self.z)**(1/2) #Designed velocity along the axis [m/s]
        
        Doppler=self.Delta0+self.k0*V_z #Detuning caused by Doppler effect.
        
    
        'Zeeman effect is the opposite of Doppler'
        Zeeman=-Doppler
                
        self.By_ideal = -1000*Zeeman*hbar/self.mu_eff #B field needed to create the Zeeman effect desired [mT]
        Bz_ideal0s=np.append(np.zeros(self.B_points_additional),self.By_ideal)
        Bz_ideal0s=np.append(Bz_ideal0s,np.zeros(self.B_points_additional))
        self.By_ideal_full = Bz_ideal0s

        if self.test==True: print('<<-- FINISHED Zeeman Core calculate_needed_B()')
        return
        
    def B_zero_crossing(self):
        # 1. Detect sign change
        # np.sign returns -1, 0 o 1. np.diff calculate difference between consecutive elements.
        # Si product is != 0, there was a sign change.
        if self.test==True:print('-->>Entering Zeeman Core zero_crossing()')
        crossings = np.where(np.diff(np.sign(self.By_ideal_short)))[0]
    
        if len(crossings) == 0:
            print("Zero crossing point not found.")
            self.zero_cross = None
            return
        if len(crossings) > 1:
            print("WARNING: Several zero crossing points found.")
        
        #┴ We take the last zero crossing point (there should be only one)
        idx = crossings[-1] 
    
        # 2. Decide which point (idx o idx+1) is closer to B=0
        val_before = abs(self.By_ideal_short[idx])
        val_after = abs(self.By_ideal_short[idx+1])
    
        if val_before < val_after:
            self.zero_cross = idx
        else:
            self.zero_cross = idx + 1
    
        if self.test==True: print('<<--EXITING Entering Zeeman Core _zero_crossing()')
      
    
    def create_magnets(self):
         """ 
             Create magnets array
         """
         if self.test==True:print('-->>Entering Zeeman Core create_magnets()')
         

         # Calling this function creates magnets from scratch
         self.magnets.clear()
         self.magnets=[[],[]]

         # Intermagnet distance:
         imd = self.positions[1]-self.positions[0]
         magnetization = self.Tmag
                 
         # Magnet 0 creation
         if self.By_ideal_short[0]>0:          # Check the polarity of the field to decide north-south pole
             magnetization = self.Tmag_neg 
         self.magnets[0].append(magpy.magnet.Cylinder(magnetization, self.size_mag, 
                                                     position=[0,self.min_magnet_distance,self.positions[0]-imd]))
         self.magnets[0][0].rotate(R.from_euler('y', 90, degrees=True))
         self.magnets[0][0].rotate(R.from_euler('z', -90, degrees=True))
         
         
         self.magnets[1].append(magpy.magnet.Cylinder(magnetization, self.size_mag, 
                                                     position=(0,-self.min_magnet_distance,self.positions[0]-imd)))
         self.magnets[1][0].rotate(R.from_euler('y', 90, degrees=True))
         self.magnets[1][0].rotate(R.from_euler('z', -90, degrees=True))      
         
         # Create magnets of the braking zone
         for i in np.arange(1,self.Npm,1):
             # Check the polarity of the field to decide north-south poles
             if self.By_ideal_short[i-1]>0:
                 magnetization = self.Tmag_neg
             else:
                 magnetization = self.Tmag
             self.magnets[0].append(magpy.magnet.Cylinder(magnetization, self.size_mag, 
                                                         position=(0,self.min_magnet_distance,self.positions[i-1])))
             self.magnets[0][i].rotate(R.from_euler('y', 90, degrees=True))
             self.magnets[0][i].rotate(R.from_euler('z', -90, degrees=True))
             self.magnets[1].append(magpy.magnet.Cylinder(magnetization, self.size_mag, 
                                                         position=(0,-self.min_magnet_distance,self.positions[i-1])))
             self.magnets[1][i].rotate(R.from_euler('y', 90, degrees=True))
             self.magnets[1][i].rotate(R.from_euler('z', -90, degrees=True))
             
             # The magnets on top of the zero cross exist as object but doesn't appear anywhere
             if i==(self.zero_cross+1): 
                 self.magnets[0][i].magnetization=[0,0,0]
                 self.magnets[0][i].dimension=[self.mag_diam,self.mag_heig]
                 self.magnets[1][i].magnetization=[0,0,0]
                 self.magnets[1][i].dimension=[self.mag_diam,self.mag_heig]
         
         # Last magnet creation. The pair is attached beyond the braking zone
         if self.By_ideal_short[-1]>0:
             magnetization = self.Tmag_neg
         
         self.magnets[0].append(magpy.magnet.Cylinder(magnetization, self.size_mag, 
                                                     position=(0,self.min_magnet_distance,(self.positions[-1]+self.positions[1]))))
         self.magnets[0][self.Npm].rotate(R.from_euler('y', 90, degrees=True))
         self.magnets[0][self.Npm].rotate(R.from_euler('z', -90, degrees=True))
         self.magnets[1].append(magpy.magnet.Cylinder(magnetization, self.size_mag, 
                                                     position=(0,-self.min_magnet_distance,(self.positions[-1]+self.positions[1]))))
         self.magnets[1][self.Npm].rotate(R.from_euler('y', 90, degrees=True))
         self.magnets[1][self.Npm].rotate(R.from_euler('z', -90, degrees=True))
          
         self.col=magpy.Collection()
         for i in self.magnets:
             self.col.add(i,override_parent=True) 

         if self.test==True: print('<<-- FINISHED Zeeman Core create_magnets()')
        
    def initial_plot(self,x,y1,y2):
        """ 
            Draws ideal B_field and also the one created by magnets actual position
            as well as the magnets themselves
        """
        if self.test==True: print('-->>Entering Zeeman Core initial_plot()')
        # In the top graphics, the B_field
        self.current_B()
        self.ax_B.plot(self.z_full*1000,self.By_ideal_full,label='B$_{y}$ ideal',color='grey',alpha=0.5)
        self.ax_B.plot(self.z_full*1000,self.By_current_full,label='B$_{y}$ simulated',color='green')
        self.ax_B.axhline(y=0,xmin=0,xmax=50,linestyle='dotted', color='gray', linewidth=0.25)
        self.ax_B.legend(loc='upper left') 

        # In the bottom graphics, the magnets position
        self.ax_B.set_ylabel('Magnetic Field (mT)')
        plt.xlabel('Z-Distance (mm)')
        self.ax_magnets.axhline(y=0,xmin=0,xmax=50,linestyle='dashed', color='gray', linewidth=1)
        self.ax_magnets.axhline(y=self.safety_distance,xmin=0,xmax=50,linestyle='dotted', color='gray', linewidth=0.5)
        self.ax_magnets.axhline(y=-self.safety_distance,xmin=0,xmax=50,linestyle='dotted', color='gray', linewidth=0.5)
        self.ax_magnets.axhspan(-self.ext_tube_radius,self.ext_tube_radius, color='blue', alpha=0.1, lw=0)
        self.ax_magnets.set_ylabel('Y-Distance to AtomicBeam (mm)')
        
        # Also the vertical lines where magnets center are    
        for i in np.arange(0,(self.Npm)+1,1):
            if i==(self.zero_cross+1):
                pass
            else:
                line_ax_B=self.ax_B.axvline(x=self.magnets[0][i].position[2],ymin=0,ymax=50,linestyle='dotted', color='gray', linewidth=0.5)
                self.magnet_lines_ax_B[i]=line_ax_B
                span_ax_B=self.ax_B.axvspan(self.magnets[0][i].position[2]-self.size_mag[0]/2,self.magnets[0][i].position[2]+self.size_mag[0]/2, color='gray', alpha=0.1, lw=0)  
                self.magnet_spans_ax_B[i]=span_ax_B
        
        # We create the rectangles red and blue for the north and south poles
        self.graphic_magnets=[]
        for i in np.arange(0,self.Npm+1,1):
            magnet=[]
            # Magnet on B_field zero cross is ignored
            if i==(self.zero_cross+1):
                magnet.append([0])
                magnet.append([0])
                pass
            else:
                magnet1,magnet2=[],[]
                line_ax_magnets=self.ax_magnets.axvline(x=self.magnets[0][i].position[2],ymin=0,ymax=50,linestyle='dotted', color='gray', linewidth=0.5)
                self.magnet_lines_ax_magnets[i]=line_ax_magnets
                span_ax_magnets=self.ax_magnets.axvspan(self.magnets[0][i].position[2]-self.size_mag[0]/2,self.magnets[0][i].position[2]+self.size_mag[0]/2, color='gray', alpha=0.1, lw=0)
                self.magnet_spans_ax_magnets[i]=span_ax_magnets
                # If B_field is negative, north pole (red) y facing down
                if self.magnets[0][i].magnetization[2]>0:
                    rect=plt.Rectangle((self.magnets[0][i].position[2]-self.size_mag[0]/2,self.magnets[0][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1]/2, facecolor='red',edgecolor=None)
                    self.ax_magnets.add_patch(rect)
                    magnet1.append(rect)
                    rect=plt.Rectangle((self.magnets[0][i].position[2]-self.size_mag[0]/2,self.magnets[0][i].position[1]), self.size_mag[0],self.size_mag[1]/2, facecolor='blue',edgecolor=None)
                    self.ax_magnets.add_patch(rect)
                    magnet1.append(rect)
                    rect=plt.Rectangle((self.magnets[0][i].position[2]-self.size_mag[0]/2,self.magnets[0][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1],edgecolor='grey',fill=False)
                    self.ax_magnets.add_patch(rect)
                    magnet1.append(rect)
                    magnet.append(magnet1)
                    rect=plt.Rectangle((self.magnets[1][i].position[2]-self.size_mag[0]/2,self.magnets[1][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1]/2, facecolor='red',edgecolor=None)
                    self.ax_magnets.add_patch(rect)
                    magnet2.append(rect)
                    rect=plt.Rectangle((self.magnets[1][i].position[2]-self.size_mag[0]/2,self.magnets[1][i].position[1]), self.size_mag[0],self.size_mag[1]/2, facecolor='blue',edgecolor=None)
                    self.ax_magnets.add_patch(rect)
                    magnet2.append(rect)
                    rect=plt.Rectangle((self.magnets[1][i].position[2]-self.size_mag[0]/2,self.magnets[1][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1], edgecolor='grey',fill=False)
                    self.ax_magnets.add_patch(rect)
                    magnet2.append(rect)
                    magnet.append(magnet2)
                
                # If B_field is positive, north pole (red) y facing up
                if self.magnets[0][i].magnetization[2]<0:
                    rect=plt.Rectangle((self.magnets[0][i].position[2]-self.size_mag[0]/2,self.magnets[0][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1]/2, facecolor='blue',edgecolor=None)
                    self.ax_magnets.add_patch(rect)
                    magnet1.append(rect)
                    rect=plt.Rectangle((self.magnets[0][i].position[2]-self.size_mag[0]/2,self.magnets[0][i].position[1]), self.size_mag[0],self.size_mag[1]/2, facecolor='red',edgecolor=None)
                    self.ax_magnets.add_patch(rect)
                    magnet1.append(rect)
                    rect=plt.Rectangle((self.magnets[0][i].position[2]-self.size_mag[0]/2,self.magnets[0][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1], edgecolor='grey',fill=False)
                    self.ax_magnets.add_patch(rect)
                    magnet1.append(rect)
                    magnet.append(magnet1)
                    rect=plt.Rectangle((self.magnets[1][i].position[2]-self.size_mag[0]/2,self.magnets[1][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1]/2, facecolor='blue',edgecolor=None)
                    self.ax_magnets.add_patch(rect)
                    magnet2.append(rect)
                    rect=plt.Rectangle((self.magnets[1][i].position[2]-self.size_mag[0]/2,self.magnets[1][i].position[1]), self.size_mag[0],self.size_mag[1]/2, facecolor='red',edgecolor=None)
                    self.ax_magnets.add_patch(rect)
                    magnet2.append(rect)
                    rect=plt.Rectangle((self.magnets[1][i].position[2]-self.size_mag[0]/2,self.magnets[1][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1], edgecolor='grey',fill=False)
                    self.ax_magnets.add_patch(rect)
                    magnet2.append(rect)
                    magnet.append(magnet2)
            self.graphic_magnets.append(magnet)
        
        # We update the canvas
        self.ax_B.relim()
        self.ax_B.margins(0.1, 0.2) 
        self.ax_magnets.relim()
        self.ax_B.autoscale_view()
        self.ax_magnets.relim()
        self.ax_magnets.margins(0.1, 0.2) 
        self.ax_magnets.autoscale_view()
        self.canvas_plot.draw()

        if self.test==True: print('<<-- FINISHED Zeeman Core initial_plot()')
   
     ###############################################################################
    
    def plot_data(self):
        ''' 
            Updates plots
        '''
        if self.test==True: print('-->>Entering Zeeman Core plot_data()')
        
        # Updates B_lines and limits in upper graph
        self.current_B()
        self.ax_B.lines[0].set_data(self.z_full*1000,self.By_ideal_full)
        self.ax_B.lines[1].set_data(self.z_full*1000,self.By_current_full)
        
        # Updates magnets position and limits in lower graph
        for i in np.arange(0,len(self.graphic_magnets),1):
            # Magnet where B_field crosses zero is ignored
            if i==(self.zero_cross+1):
                pass
            # The rest are updated
            else:
                
                self.graphic_magnets[i][0][0].set_y(self.magnets[0][i].position[1]-self.size_mag[1]/2)
                self.graphic_magnets[i][0][1].set_y(self.magnets[0][i].position[1])
                self.graphic_magnets[i][0][2].set_y(self.magnets[0][i].position[1]-self.size_mag[1]/2)
                self.graphic_magnets[i][1][0].set_y(self.magnets[1][i].position[1]-self.size_mag[1]/2)
                self.graphic_magnets[i][1][1].set_y(self.magnets[1][i].position[1])
                self.graphic_magnets[i][1][2].set_y(self.magnets[1][i].position[1]-self.size_mag[1]/2)
                self.magnet_lines_ax_B[i].set_xdata([self.magnets[0][i].position[2],self.magnets[0][i].position[2]])
                self.magnet_spans_ax_B[i].remove()
                span_ax_B=self.ax_B.axvspan(self.magnets[0][i].position[2]-self.size_mag[0]/2,self.magnets[0][i].position[2]+self.size_mag[0]/2, color='gray', alpha=0.1, lw=0)  
                self.magnet_spans_ax_B[i]=span_ax_B
                self.graphic_magnets[i][0][0].set_x(self.magnets[0][i].position[2]-self.size_mag[0]/2)
                self.graphic_magnets[i][0][1].set_x(self.magnets[0][i].position[2]-self.size_mag[0]/2)
                self.graphic_magnets[i][0][2].set_x(self.magnets[0][i].position[2]-self.size_mag[0]/2)
                self.graphic_magnets[i][1][0].set_x(self.magnets[1][i].position[2]-self.size_mag[0]/2)
                self.graphic_magnets[i][1][1].set_x(self.magnets[1][i].position[2]-self.size_mag[0]/2)
                self.graphic_magnets[i][1][2].set_x(self.magnets[1][i].position[2]-self.size_mag[0]/2)
                self.magnet_lines_ax_magnets[i].set_xdata([self.magnets[0][i].position[2],self.magnets[0][i].position[2]])
                self.magnet_spans_ax_magnets[i].remove()
                span_ax_magnets=self.ax_magnets.axvspan(self.magnets[0][i].position[2]-self.size_mag[0]/2,self.magnets[0][i].position[2]+self.size_mag[0]/2, color='gray', alpha=0.1, lw=0)  
                self.magnet_spans_ax_magnets[i]=span_ax_magnets
        
        # We update the canvas
        self.ax_B.relim()
        self.ax_B.margins(0.1, 0.2) 
        self.ax_B.autoscale_view()
        self.ax_magnets.relim()
        self.ax_magnets.margins(0.1, 0.2) 
        self.ax_magnets.autoscale_view()
        self.canvas_plot.draw_idle()
        self.canvas_plot.flush_events()
        
        if self.test==True: print('<<--EXITING Zeeman Core plot_data()')
    

    ###############################################################################
    'Functions to move magnets from present position'
    ###############################################################################
    def aproximate(self,i,dist):
        # if self.test==True: print('-->>Entering Zeeman Core aproximate()')
        self.magnets[0][i].move([0,-dist,0])
        self.magnets[1][i].move([0,dist,0])
        # if self.test==True: print('<<--EXITING Zeeman Core aproximate()')
    
    def separate(self,i,dist):
        # if self.test==True: print('-->>Entering Zeeman Core separate()')
        self.magnets[0][i].move([0,dist,0])
        self.magnets[1][i].move([0,-dist,0])
        # if self.test==True: print('<<--EXITING Zeeman Core separate()')

    def horizontal(self,i,dist):
        # if self.test==True: print('-->>Entering Zeeman Core horizontal()')
        self.magnets[0][i].move([0,0,dist])
        self.magnets[1][i].move([0,0,dist])
        # if self.test==True: print('<<--EXITING Zeeman Core horizontal()')

    
    def move_magnet_V(self,num,dist):
        '''
            Move magnets vertically and recalculates B_field and update plots
        '''
        if self.test==True: print('-->>Entering Zeeman Core move_magnet_V()')
        if dist > 0:
            self.separate(num,dist)   
        else:
            self.aproximate(num,-dist) 

        self.current_B()

        self.plot_data()
        
        if self.test==True: print('<<--EXITING Zeeman Core move_magnet_V()')
           
    def move_magnet_H(self,num,dist):
        '''
            Move magnets horizontally and recalculates B_field and update plots
        '''
        if self.test==True: print('-->>Entering Zeeman Core move_magnet_H()')
        self.horizontal(num,dist) 

        self.plot_data()
        if self.test==True: print('<<--EXITING Zeeman Core move_magnet_H()')

    

    def preliminary_position(self):
        ''' 
            We set the preliminary position for magnets and initial calculations
        '''
        if self.test==True: print('-->>Entering Zeeman Core preliminary_position()')
        
        # Calculate current field
        self.current_B()
        
        # We draw it
        self.initial_plot(1000*self.z,self.By_ideal,self.By_current)
        if self.test==True: print('<<-- FINISHED Zeeman Core preliminary_position()')

    def optimize_magnets(self,displ,sign,rev,iters,progress_callback=None):
        """ 
        This function moves magnets back and forth vertically to make generated B 
        as closer as possible to ideal B
        """      
        if self.test==True: print('-->>Entering Zeeman Core optimize_magnets()')
        print('-------------------OPTIMISING--------------------------')
        print('--- Moving magnets each ', displ,'mm')
        if sign>0:
            print('--- Default direction separating from atomic axis...')
        else:
            print('--- Default direction aproximating to atomic axis...')
        if rev==False:
            print('--- Staring by magnets closer to the oven...')
        else:
            print('--- Staring by magnets farther from the oven...')
        
        print('--- Number of iterations finding no improvement...', iters)
        print('--------------------------------------------------------')
        
        # Minimum number of iterations and separation distance from first
        # and last magnet from their closest one
        iter_mins=0

        iterations=0
        optimized=False
        
        # This array contains two deviations: 0 minimum obtained and 1 present one
        B_tbo_act=self.col.getB(1000*self.z_axis)
        desv=np.linalg.norm(B_tbo_act[:,1]-self.By_ideal)*np.ones(2)
        
        # This array stores the positions where B has been optimum at present time
        pos_mins=np.zeros(self.Npm+1,dtype='float')
        for n in np.arange(0,self.Npm+1,1):
            pos_mins[n]=self.magnets[0][n].position[1]

        # We decide here to move first initial or last magnets
        if rev==True:
            orden=np.arange(int(len(self.col)/2)-1,-1,-1)
        else:
            orden=np.arange(0,self.Npm+1,1)

        for n in orden:
            pos_mins[n]=self.magnets[0][n].position[1]
        
        # While we don't get an optimal position, we keep on moving magnets
        while (optimized==False) and (iterations < self.iterations_max): 
            B_tbo_act=self.col.getB(1000*self.z_axis)
            desv[1]=np.linalg.norm(B_tbo_act[:,1]-self.By_ideal)
            for i in np.arange(0,int(len(self.col)/2),1):
                # We pass the magnets over zero_cross
                if (i==self.zero_cross+1):
                    pass
                # We move the rest
                else:
                    B_tbo_act=self.col.getB(1000*self.z_axis)
                    # We try separating (or joining, depending on "sign").
                    self.separate(i,sign*displ)
                    # We stop if the magnet is too close to the vacuum tube
                    if self.magnets[0][i].position[1]<self.min_magnet_distance:
                        self.magnets[0][i].position[1]=self.min_magnet_distance
                        self.magnets[1][i].position[1]=-self.min_magnet_distance
                    # First two magnets are moved together (explanation on user manual)
                    if i==1:
                        self.magnets[0][0].position[1]=self.magnets[0][1].position[1]-self.sep_ini
                        self.magnets[1][0].position[1]=self.magnets[1][1].position[1]+self.sep_ini
                    # Last two magnets are moved together (explanation on user manual)
                    if i==self.Npm-1:
                        self.magnets[0][self.Npm].position[1]=self.magnets[0][self.Npm-1].position[1]-self.sep_last
                        self.magnets[1][self.Npm].position[1]=self.magnets[1][self.Npm-1].position[1]+self.sep_last
                    new_B_tbo=self.col.getB(1000*self.z_axis)
                    # If we get no improvements...
                    if round(np.linalg.norm(B_tbo_act[:,1]-self.By_ideal),2) < round(np.linalg.norm(new_B_tbo[:,1]-self.By_ideal),2):
                        # We move in the opposite direction
                        self.aproximate(i,2*sign*displ)
                        if self.magnets[0][i].position[1]<self.min_magnet_distance:
                             self.magnets[0][i].position[1]=self.min_magnet_distance
                             self.magnets[1][i].position[1]=-self.min_magnet_distance
                        # First two magnets are moved together (explanation on user manual)
                        if i==1:
                            if self.magnets[0][1].position[1]-self.sep_ini >= self.min_magnet_distance:
                                self.magnets[0][0].position[1]=self.magnets[0][1].position[1]-self.sep_ini
                                self.magnets[1][0].position[1]=self.magnets[1][1].position[1]+self.sep_ini
                            else:
                                self.magnets[0][0].position[1]=self.min_magnet_distance
                                self.magnets[1][0].position[1]=-self.min_magnet_distance
                        # Last two magnets are moved together (explanation on user manual)
                        if i==self.Npm-1:
                            if self.magnets[0][self.Npm-1].position[1]-self.sep_last >= self.min_magnet_distance:
                                self.magnets[0][self.Npm].position[1]=self.magnets[0][self.Npm-1].position[1]-self.sep_last
                                self.magnets[1][self.Npm].position[1]=self.magnets[1][self.Npm-1].position[1]+self.sep_last
                            else:
                                self.magnets[0][self.Npm].position[1]=self.min_magnet_distance
                                self.magnets[1][self.Npm].position[1]=-self.min_magnet_distance
                        new_B_tbo=self.col.getB(1000*self.z_axis)
                        if round(np.linalg.norm(B_tbo_act[:,1]-self.By_ideal),2) < round(np.linalg.norm(new_B_tbo[:,1]-self.By_ideal),2):
                            # If we get no improvements we leave magnets where they were initially.
                            self.separate(i,sign*displ)
                            if self.magnets[0][i].position[1]<self.min_magnet_distance:
                               self.magnets[0][i].position[1]=self.min_magnet_distance
                               self.magnets[1][i].position[1]=-self.min_magnet_distance
                           # First two magnets are moved together (explanation on user manual)
                            if i==1:
                               self.magnets[0][0].position[1]=self.magnets[0][1].position[1]-self.sep_ini
                               self.magnets[1][0].position[1]=self.magnets[1][1].position[1]+self.sep_ini
                           # Last two magnets are moved together (explanation on user manual)
                            if i==self.Npm-1:    
                               self.magnets[0][self.Npm].position[1]=self.magnets[0][self.Npm-1].position[1]-self.sep_last
                               self.magnets[1][self.Npm].position[1]=self.magnets[1][self.Npm-1].position[1]+self.sep_last
                  
            new_B_tbo = self.col.getB(1000*self.z_axis)
            
            # We update the graphs
            self.By_current = new_B_tbo[:,1]
            self.plot_data()

            # We calculate the new deviation from the ideal B_field
            desv[1] = np.linalg.norm(new_B_tbo[:,1]-self.By_ideal)
            
            # If deviation is better than previous one, we update it and reset the counter.
            if round(desv[1],2) < round(desv[0],2):
                desv[0]=desv[1]
                iter_mins=0
                # We save the magnets positions wehere minimum deviation was found.
                for n in np.arange(0,self.Npm+1,1):
                    if self.magnets[0][n].position[1] >= self.min_magnet_distance:
                        pos_mins[n]=self.magnets[0][n].position[1]
                    else:
                        pos_mins[n]=self.min_magnet_distance
            # Otherwise, we add 1 to the iterations chances we couldn't improve
            else:
                iter_mins+=1
            
            # If we deplete the chances to look for an improvement, we consider we are optimum
            if iter_mins==iters:
                optimized=True
                for n in np.arange(0,self.Npm+1,1):
                    if pos_mins[n] >= self.min_magnet_distance:
                        self.magnets[0][n].position[1]=pos_mins[n]
                        self.magnets[1][n].position[1]=-pos_mins[n]
                    else:
                        self.magnets[0][n].position[1]=self.min_magnet_distance
                        self.magnets[1][n].position[1]=-self.min_magnet_distance
            print('IterTOT#', iterations, ' || IterSeries', iter_mins, '|| Desv {:.2f}'.format(desv[1]))
             
            iterations+=1
            
            if progress_callback is not None:
                # Limit self.iterations_max
                current_percent = min(100, 100*iterations/self.iterations_max)
                progress_callback(current_percent)
            
            if self.break_simulations == True:
                if self.test: print("Cancellation detected: Restoring magnets to last stable position...")
                
                # Restore magnet to last previous valid position
                for n in np.arange(0, self.Npm + 1, 1):
                    if pos_mins[n] >= self.min_magnet_distance:
                        self.magnets[0][n].position[1] = pos_mins[n]
                        self.magnets[1][n].position[1] = -pos_mins[n]
                    else:
                        self.magnets[0][n].position[1]=self.min_magnet_distance
                        self.magnets[1][n].position[1]=-self.min_magnet_distance
                # Recalculate B field with restored positions
                self.By_current = self.col.getB(1000 * self.z_axis)[:, 1]
                return

        # We update the graphics
        self.By_current = new_B_tbo[:,1]
        self.plot_data()
       
        if self.test==True: print('<<-- FINISHED Zeeman Core optimize_magnets()')
         
        return True

    def optimal_position(self,progress_callback=None):
        '''
           We call several times to the optimizing function with progressively lower
           distances, order and movement to move the magnets, as well as
           the iterations (chances to move withous improvements)
        '''
        # 1. Define the 5 stages of optimization
        # Format: (displacement, sign, reverse, iterations)
        stages = [
            (self.displ * 50,  1, False, 3), # Stage 1: 0% - 20%
            (self.displ * 20, -1, True,  3), # Stage 2: 20% - 40%
            (self.displ * 10,  1, False, 3), # Stage 3: 40% - 60%
            (self.displ,      -1, False, 3), # Stage 4: 60% - 80%
            (self.displ,       1, True,  3)  # Stage 5: 80% - 100%
        ]
        
        total_stages = len(stages) # 5
        stage_weight = 100.0 / total_stages # Each stage is worth 20% of the total

        # 2. Iterate through stages
        for i, (d, s, r, it) in enumerate(stages):
            
            if self.break_simulations: break

            # --- THE WRAPPER ---
            # We define a temporary function that converts the inner 0-100% 
            # into the global percentage for this specific stage.
            # Example: If we are in Stage 2 (starts at 20%), and inner progress is 50%,
            # Global = 20 + (50 * 0.2) = 30%
            
            def stage_callback(inner_percent):
                if progress_callback:
                    # Calculate start percentage for this stage (e.g., 0, 20, 40...)
                    base_progress = i * stage_weight
                    
                    # Calculate added progress (inner_percent is 0-100)
                    added_progress = (inner_percent / 100.0) * stage_weight
                    
                    # Send total integer to GUI
                    total = int(base_progress + added_progress)
                    progress_callback(total)

            # 3. Call the worker function passing our wrapper
            self.optimize_magnets(d, s, r, it, progress_callback=stage_callback)
        
        self.break_simulations = False
        print('Optimization process ended')
        
        # Ensure we hit 100% at the end
        if progress_callback: progress_callback(100)
        
        if self.test==True: print('<<-- FINISHED Zeeman Core optimal_position()')
   

    def search_position_magnet(self,ax):
        '''
            We detect maximum and minimum values of y position of magnets
            to create graphs proportionally
        '''
        if self.test==True: print('-->>Entering Zeeman Core search_position_magnet_y()')
        pos_min=self.magnets[1][0].position[ax]
        pos_max=self.magnets[0][0].position[ax]
        for i in self.magnets[1]:            
            if i.position[ax] < pos_min:
                pos_min=i.position[ax]
        for i in self.magnets[0]:
            if i.position[ax] > pos_max:
                pos_max = i.position[ax]
        pos_hop = self.magnets[0][1].position[ax] - self.magnets[0][0].position[ax]
        if self.test==True: print('<<--EXITING Zeeman Core search_position_magnet()')
        return pos_min, pos_max, pos_hop

    def draw_2D(self,x,y1,y2,magnets):
        ''' 
            Function for the initial drawing
        '''
        if self.test==True: print('-->>Entering Zeeman Core draw_2D()')
        # We create the figure
        now=dtm.now()
        time_stamp = now.strftime("%d-%m-%Y %H:%M:%S")
        title='By-field optimized ('+str(time_stamp)+')'
        plt.ion()
        self.fig_2D=plt.figure(title,figsize=(9,10),layout='constrained')
        self.fig_2D.suptitle(title)
        # We create 2 subplots: for the B_field and for the magnets positions
        self.subplot_2D_ax_B,self.subplot_2D_ax_magnets=self.fig_2D.subplots(nrows=2,sharex=True)
        
        # We draw the ideal and current B field in the upper subplot
        self.subplot_2D_ax_B.plot(x,y1,label='B_ideal',color='grey',alpha=0.5)
        self.subplot_2D_ax_B.plot(x,y2,label='B_calculated',color='green')
        self.subplot_2D_ax_B.axhline(y=0,xmin=0,xmax=50,linestyle='dotted', color='gray', linewidth=0.25)        
        self.subplot_2D_ax_B.autoscale_view()
        self.subplot_2D_ax_B.set_ylabel('Magnetic Field (mT)')
        self.subplot_2D_ax_B.legend(loc='upper left')
        plt.xlabel('Z-Distance (mm)')
        
        # We draw the magnets positions in the bottom subplot
        self.subplot_2D_ax_magnets.axhline(y=0,xmin=0,xmax=50,linestyle='dotted', color='gray', linewidth=0.5)
        self.subplot_2D_ax_magnets.axhline(y=self.safety_distance,xmin=0,xmax=50,linestyle='dotted', color='gray', linewidth=0.5)
        self.subplot_2D_ax_magnets.axhline(y=-self.safety_distance,xmin=0,xmax=50,linestyle='dotted', color='gray', linewidth=0.5)
        self.subplot_2D_ax_magnets.axhspan(-self.ext_tube_radius,self.ext_tube_radius, color='blue', alpha=0.2, lw=0)
        self.subplot_2D_ax_magnets.set_ylabel('Y-Distance to AtomicBeam (mm)')
        
        # vertical lines are drawed where the magnets are positioned   
        for i in np.arange(0,self.Npm+1,1):
            if i==(self.zero_cross+1):
                pass
            else:
                self.subplot_2D_ax_B.axvline(x=magnets[0][i].position[2],ymin=0,ymax=50,linestyle='dotted', color='gray', linewidth=0.5)
                self.subplot_2D_ax_B.axvspan(magnets[0][i].position[2]-self.size_mag[0]/2,magnets[0][i].position[2]+self.size_mag[0]/2, color='gray', alpha=0.1, lw=0)  
        
        # We create a list to draw rectangles for each magnet
        graphic_magnets=[]
        for i in np.arange(0,self.Npm+1,1):
            magnet=[]
            # we pass the magnet over zero cross position
            if i==(self.zero_cross+1):
                magnet.append([0])
                magnet.append([0])
                pass
            else:
                magnet1,magnet2=[],[]                
                # If B_field is negative, magnets are oriented north pole (red) facing down
                if magnets[0][i].magnetization[2]>0:
                    rect=plt.Rectangle((magnets[0][i].position[2]-self.size_mag[0]/2,magnets[0][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1]/2, facecolor='red',edgecolor=None)
                    self.subplot_2D_ax_magnets.add_patch(rect)
                    magnet1.append(rect)
                    rect=plt.Rectangle((magnets[0][i].position[2]-self.size_mag[0]/2,magnets[0][i].position[1]), self.size_mag[0],self.size_mag[1]/2, facecolor='blue',edgecolor=None)
                    self.subplot_2D_ax_magnets.add_patch(rect)
                    magnet1.append(rect)
                    rect=plt.Rectangle((magnets[0][i].position[2]-self.size_mag[0]/2,magnets[0][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1],edgecolor='grey',fill=False)
                    self.subplot_2D_ax_magnets.add_patch(rect)
                    magnet1.append(rect)
                    magnet.append(magnet1)
                    rect=plt.Rectangle((magnets[1][i].position[2]-self.size_mag[0]/2,magnets[1][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1]/2, facecolor='red',edgecolor=None)
                    self.subplot_2D_ax_magnets.add_patch(rect)
                    magnet2.append(rect)
                    rect=plt.Rectangle((magnets[1][i].position[2]-self.size_mag[0]/2,magnets[1][i].position[1]), self.size_mag[0],self.size_mag[1]/2, facecolor='blue',edgecolor=None)
                    self.subplot_2D_ax_magnets.add_patch(rect)
                    magnet2.append(rect)
                    rect=plt.Rectangle((magnets[1][i].position[2]-self.size_mag[0]/2,magnets[1][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1], edgecolor='grey',fill=False)
                    self.subplot_2D_ax_magnets.add_patch(rect)
                    magnet2.append(rect)
                    magnet.append(magnet2)
                # If B_field is positive, magnets are oriented north pole (red) facing up
                if magnets[0][i].magnetization[2]<0:
                    rect=plt.Rectangle((magnets[0][i].position[2]-self.size_mag[0]/2,magnets[0][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1]/2, facecolor='blue',edgecolor=None)
                    self.subplot_2D_ax_magnets.add_patch(rect)
                    magnet1.append(rect)
                    rect=plt.Rectangle((magnets[0][i].position[2]-self.size_mag[0]/2,magnets[0][i].position[1]), self.size_mag[0],self.size_mag[1]/2, facecolor='red',edgecolor=None)
                    self.subplot_2D_ax_magnets.add_patch(rect)
                    magnet1.append(rect)
                    rect=plt.Rectangle((magnets[0][i].position[2]-self.size_mag[0]/2,magnets[0][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1], edgecolor='grey',fill=False)
                    self.subplot_2D_ax_magnets.add_patch(rect)
                    magnet1.append(rect)
                    magnet.append(magnet1)
                    rect=plt.Rectangle((magnets[1][i].position[2]-self.size_mag[0]/2,magnets[1][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1]/2, facecolor='blue',edgecolor=None)
                    self.subplot_2D_ax_magnets.add_patch(rect)
                    magnet2.append(rect)
                    rect=plt.Rectangle((magnets[1][i].position[2]-self.size_mag[0]/2,magnets[1][i].position[1]), self.size_mag[0],self.size_mag[1]/2, facecolor='red',edgecolor=None)
                    self.subplot_2D_ax_magnets.add_patch(rect)
                    magnet2.append(rect)
                    rect=plt.Rectangle((magnets[1][i].position[2]-self.size_mag[0]/2,magnets[1][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1], edgecolor='grey',fill=False)
                    self.subplot_2D_ax_magnets.add_patch(rect)
                    magnet2.append(rect)
                    magnet.append(magnet2)
            graphic_magnets.append(magnet)
        
        self.subplot_2D_ax_B.margins(0.1, 0.2)       
        self.subplot_2D_ax_magnets.margins(0.1,0.2)
        # Recalculate limits
        self.subplot_2D_ax_magnets.relim() 
        self.subplot_2D_ax_magnets.autoscale_view()

        # Adjust top graph
        self.subplot_2D_ax_B.relim()
        self.subplot_2D_ax_B.autoscale_view()
        self.fig_2D.show()
        if self.test==True: print('<<-- FINISHED Zeeman Core draw_2D()')



    def B_field_2D_lines_drawing(self):
        '''
            Creates a 2D graph with the lines of the B_field on top of magnets graph (lower one)
            as well as a full B field line
        '''
        if self.test==True: print('-->>Entering Zeeman Core B_field_2D_lines_drawing()')

        self.current_B()
        self.draw_2D(1000*self.z,self.By_ideal,self.By_current,self.magnets)

        # We add some points before and after the braking zone (0-self.LZ)
        Bz_ideal0s=np.append(np.zeros(self.B_points_additional),self.By_ideal)
        Bz_ideal0s=np.append(Bz_ideal0s,np.zeros(self.B_points_additional))
        
        if self.test==True: print('*******************Bz_ideal0s ',Bz_ideal0s)
        if self.test==True: print('*******************self.By_ideal_full ',self.By_ideal_full)

        # Now we can draw them
        self.fig_2D.axes[0].lines[0].set_data(1000*self.z_full,Bz_ideal0s) 
        self.fig_2D.axes[0].lines[1].set_data(1000*self.z_full,self.By_current_full) 
        
        # And calculate how far is the real B_field vs the ideal one
        print('FINAL deviation within the braking zone', np.linalg.norm(self.By_current-self.By_ideal))
        print('Total FINAL deviation', np.linalg.norm(self.By_current_full-self.By_ideal_full))

        # We scale the drawing        
        self.subplot_2D_ax_B.autoscale_view()

        # We look for the max and min position in the magnets
        self.y_min,self.y_max,self.y_salto = self.search_position_magnet(1)
        self.y_salto=2*self.magnets[0][1].dimension[1]
        self.z_min,self.z_max,self.z_salto = self.search_position_magnet(2)
        
        
        # We create the axis in y & z for the grid
        ys = np.linspace(1.2*self.y_min, 1.2*self.y_max, int(self.y_max-self.y_min+1))
        zs = 1000*self.z_full
        grid = np.array([[(0,y,z) for y in ys] for z in zs])
        
        # We calculate B_field along all the grid
        B = self.col.getB(grid)
        Bz=np.transpose(B[:,:,2])
        By=np.transpose(B[:,:,1])
        ampB = np.transpose(np.linalg.norm(B, axis=2))
        
        # We create grid for the streamplot: create and transpose for z-horizontal
        Z,Y=np.meshgrid(zs,ys)
        self.subplot_2D_ax_magnets.streamplot(Z, Y, Bz, By,density = 8, color = np.log(ampB),
                                              linewidth=0.5, cmap='winter',zorder=1)
        
        # We draw the magnets on top
        for i in range(len(self.magnets[0])):
            if i==(self.zero_cross+1):
                pass
            else:
                self.subplot_2D_ax_magnets.axvline(x=self.magnets[0][i].position[2],ymin=0,ymax=50,linestyle='dashed', color='gray', linewidth=0.5,zorder=1)
                self.subplot_2D_ax_magnets.axvspan(self.magnets[0][i].position[2]-self.size_mag[0]/2,self.magnets[0][i].position[2]+self.size_mag[0]/2, color='gray', alpha=0.1, lw=0,zorder=0)  
        for i in range(0,self.Npm+1,1):
            if i==self.zero_cross+1:
                pass
            else:
                self.subplot_2D_ax_magnets.text(self.magnets[0][i].position[2],0,round(self.magnets[0][i].position[1],1),color='red',fontsize=14,horizontalalignment='center')
                if self.magnets[0][i].magnetization[2]>0:
                    self.subplot_2D_ax_magnets.add_patch(patches.Rectangle((self.magnets[0][i].position[2]-self.size_mag[0]/2,self.magnets[0][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1]/2, facecolor='red',edgecolor=None,zorder=2))
                    self.subplot_2D_ax_magnets.add_patch(patches.Rectangle((self.magnets[0][i].position[2]-self.size_mag[0]/2,self.magnets[0][i].position[1]), self.size_mag[0],self.size_mag[1]/2, facecolor='blue',edgecolor=None,zorder=2))
                    self.subplot_2D_ax_magnets.add_patch(patches.Rectangle((self.magnets[0][i].position[2]-self.size_mag[0]/2,self.magnets[0][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1], edgecolor='grey',fill=False,zorder=2))
                    self.subplot_2D_ax_magnets.add_patch(patches.Rectangle((self.magnets[1][i].position[2]-self.size_mag[0]/2,self.magnets[1][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1]/2, facecolor='red',edgecolor=None,zorder=2))
                    self.subplot_2D_ax_magnets.add_patch(patches.Rectangle((self.magnets[1][i].position[2]-self.size_mag[0]/2,self.magnets[1][i].position[1]), self.size_mag[0],self.size_mag[1]/2, facecolor='blue',edgecolor=None,zorder=2))
                    self.subplot_2D_ax_magnets.add_patch(patches.Rectangle((self.magnets[1][i].position[2]-self.size_mag[0]/2,self.magnets[1][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1], edgecolor='grey',fill=False,zorder=2))
                if self.magnets[0][i].magnetization[2]<0:
                    self.subplot_2D_ax_magnets.add_patch(patches.Rectangle((self.magnets[0][i].position[2]-self.size_mag[0]/2,self.magnets[0][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1]/2, facecolor='blue',edgecolor=None,zorder=2))
                    self.subplot_2D_ax_magnets.add_patch(patches.Rectangle((self.magnets[0][i].position[2]-self.size_mag[0]/2,self.magnets[0][i].position[1]), self.size_mag[0],self.size_mag[1]/2, facecolor='red',edgecolor=None,zorder=2))
                    self.subplot_2D_ax_magnets.add_patch(patches.Rectangle((self.magnets[0][i].position[2]-self.size_mag[0]/2,self.magnets[0][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1], edgecolor='grey',fill=False,zorder=2))
                    self.subplot_2D_ax_magnets.add_patch(patches.Rectangle((self.magnets[1][i].position[2]-self.size_mag[0]/2,self.magnets[1][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1]/2, facecolor='blue',edgecolor=None,zorder=2))
                    self.subplot_2D_ax_magnets.add_patch(patches.Rectangle((self.magnets[1][i].position[2]-self.size_mag[0]/2,self.magnets[1][i].position[1]), self.size_mag[0],self.size_mag[1]/2, facecolor='red',edgecolor=None,zorder=2))
                    self.subplot_2D_ax_magnets.add_patch(patches.Rectangle((self.magnets[1][i].position[2]-self.size_mag[0]/2,self.magnets[1][i].position[1]-self.size_mag[1]/2), self.size_mag[0], self.size_mag[1], edgecolor='grey',fill=False,zorder=2))
                    # 1. Aplicar márgenes (el 10% que querías)
        self.subplot_2D_ax_B.relim()
        self.subplot_2D_ax_B.margins(0.1, 0.2)       
        self.subplot_2D_ax_magnets.margins(0.1,0.2)
        # Recalculate limits
        self.subplot_2D_ax_magnets.relim() 
        self.subplot_2D_ax_magnets.autoscale_view()

        # Adjust top subplot
        self.subplot_2D_ax_B.relim()
        self.subplot_2D_ax_B.autoscale_view()
        self.fig_2D.show()
        
        if self.test==True: print('<<-- FINISHED Zeeman Core B_field_2D_lines_drawing()')
        

    def atomic_kinetics(self, progress_callback=None):
        ''' 
            We proceed to simulate atoms kinetics 
            Atoms are supposed to move along z-axis
        '''
        t0=dtm.now()
        if self.test==True: print('-->>Entering Zeeman Core atomic_kinetics()')
               
        self.current_B() # Update field values
        
        # We create the array of velocities
        prop = 1 / (self.N_vel - 1)
        vector = np.linspace(prop, 1 + prop, self.N_vel)
        self.Vz = np.round(self.V_cap * vector)
        Vr = np.zeros(len(self.Vz))  # No radial speed: Vr = 0
        theta = np.zeros(len(self.Vz))  # No azimuthal speed: Vtheta = 0
        self.N = len(self.Vz)
    
        # Matrix creation: position, speed, acceleration, detuning 
        self.Atoms_position = np.zeros((self.N, self.Nt, 3))  # Atoms position
        self.Atoms_speed = np.zeros((self.N, self.Nt, 3))  # Atoms speed       
        acel_minus = np.zeros((self.N, self.Nt))  # Atoms acceleration (braking)
        acel_tot = np.zeros((self.N, self.Nt))  # Atoms acceleration (braking)
        self.detuning_minus = np.zeros((self.N, self.Nt))  # Detuning perceived by atoms
        
        if self.use_sigma_plus:
            acel_plus = np.zeros((self.N, self.Nt))  # Atoms acceleration (braking)
            self.detuning_plus = np.zeros((self.N, self.Nt))  # Detuning perceived by atoms
        
        # Time vector generation
        time_z = np.arange(0, self.Nt * self.dt, self.dt)
    
        n = 0
        
        # Matrix initialization
    
        # 1. Initial position: all atoms start at z=-initial_position
        self.Atoms_position[:, 0, 2] = 1e-3*self.atoms_initial_z_position
    
        # 2. Initial B_field, detuning and Rabi frequency
        # We need an array of positions for the B_field perceived by each atom
        initial_pos_xyz = np.zeros((self.N, 3))
        initial_pos_xyz[:, 2] = 1000 * self.atoms_initial_z_position

        B_fields = 1e-3 * self.col.getB(initial_pos_xyz)  # (self.N, 3)
        self.detuning_minus[:, 0] = self.Delta0 + self.k0 * self.Atoms_speed[:, 0, 2] - self.mu_eff * B_fields[:, 1] / hbar       
                
        if self.use_sigma_plus:
            self.detuning_plus[:, 0] = self.Delta0 + self.k0 * self.Atoms_speed[:, 0, 2] + self.mu_eff * B_fields[:, 1] / hbar
        
        # 3. Initial velocity (matrix initiated by vectors)
        self.Atoms_speed[:, 0, 0] = Vr
        self.Atoms_speed[:, 0, 1] = theta
        self.Atoms_speed[:, 0, 2] = self.Vz
    
        
        # 4. Atom kinetics: loop over time
        
        for i in range(1, len(time_z) - 1):
            
            # a) Calculate new atoms positions
            self.Atoms_position[:, i, :] = self.Atoms_position[:, i - 1, :] + self.Atoms_speed[:, i - 1, :] * self.dt
    
            # b) Calculate B_field on new positions (only z-movement)

            positions_xyz = np.zeros((self.N, 3))
            positions_xyz[:, 2] = 1000 * self.Atoms_position[:, i, 2]
            
            B_fields = 1e-3 * self.col.getB(positions_xyz) # Size (self.N, 3)
    
            # c) Calculate new detuning 
            self.detuning_minus[:, i - 1] = self.Delta0 + self.k0 * self.Atoms_speed[:, i - 1, 2] - self.mu_eff * B_fields[:, 1] / hbar            
            
            if self.use_sigma_plus:
                self.detuning_plus[:, i - 1] = self.Delta0 + self.k0 * self.Atoms_speed[:, i - 1, 2] + self.mu_eff * B_fields[:, 1] / hbar    
                acel_plus[:, i] = -(1 / self.m) * self.s_max / (1 + self.s_max + 4 * self.detuning_plus[:, i - 1] ** 2 / self.GAMMA0 ** 2) * (hbar * self.k0 * self.GAMMA0 / 2)
            # d) Calculare new acceleration
            acel_minus[:, i] = -(1 / self.m) * self.s_max / (1 + self.s_max + 4 * self.detuning_minus[:, i - 1] ** 2 / self.GAMMA0 ** 2) * (hbar * self.k0 * self.GAMMA0 / 2)           
            
            if self.use_sigma_plus:
                acel_tot[:,i]=acel_minus[:,i] +acel_plus[:,i]
            else:
                acel_tot[:,i]=acel_minus[:,i]
                
            # e) Calculate new speed (in z-axis, no Vradial nor Vazimuthal)
            self.Atoms_speed[:, i, 0] = self.Atoms_speed[:, i - 1, 0]
            self.Atoms_speed[:, i, 1] = self.Atoms_speed[:, i - 1, 1]
            self.Atoms_speed[:, i, 2] = self.Atoms_speed[:, i - 1, 2] + acel_tot[:, i] * self.dt
    
            # Step just to follow up simulation progression
            if i > 100 * n:
                if progress_callback is not None:
                # Calculate percentage (0-100)
                    percent = int((i / len(time_z)) * 100)
                    progress_callback(percent)
                
                print("{:.2f}".format(100 * i / len(time_z)), ' %  ||', i, '/', len(time_z))
                n += 1
            
            QApplication.processEvents()
            if self.break_simulations == True:
                self.break_simulations = False
                print("Atoms kinetics simulation interrupted.")
                return
        
        t1=dtm.now()
        print('Elapsed time in atomic_kinetics calculation (prints, 100)', t1-t0)
        print("100.00 %  || Atoms kinetics simulation ended.")
        
        return
        
    def plot_atomic_kinetics(self):
        # Plotting atomic kinetics
        
        # Calculation of By field for plotting
        B_3d = self.col.getB(1000 * self.z_axis_full)
        B = B_3d[:, 1]
    
        # Graphics creation
        now=dtm.now()
        time_stamp = now.strftime("%d-%m-%Y %H:%M:%S")
        title='Atoms deceleration in a Zeeman Slower ('+str(time_stamp)+')'
        plt.ion()
        self.fig_vels=plt.figure(title,figsize=(16,9))
        self.fig_vels.suptitle(title)
        self.fig_vels.text(x=0.5,y=0.93,s='P = ' + str(int(self.P*1e3)) + ' mW  |  Vcap = ' + str(self.V_cap) + ' m/s  |  Vfin = ' + str(self.V_fin) + ' m/s  |  d0 = ' + str(self.d0_Mhz) + ' MHz',ha='center',fontsize=10,fontstyle='italic')
        subplots_vels=self.fig_vels.subplots(nrows=1) 
    
        END = round(0.99 * self.Nt)
        
        for k in range(0, self.N):
            subplots_vels.plot(np.transpose(1e3*self.Atoms_position[k, :END, 2]), np.transpose(self.Atoms_speed[k, :END, 2]), label=str(int(self.Vz[k]))+' m/s')
        
        
        try:
            index_end_speed_array = np.where(self.Atoms_position[len(self.Vz)-2,:,2]>self.LZ*1.2)
            index_end_speed = int(index_end_speed_array[0][0])            
        except:
            index_end_speed=len(self.Atoms_position[len(self.Vz)-2,:,2])-2
        
        if self.test == True: print ('Index end speed ', index_end_speed)
        if self.test == True: print ('Position end speed ',1e3*self.Atoms_position[len(self.Vz)-2,index_end_speed,2]*0.95)
        if self.test == True: print('y_pos_text', self.Atoms_speed[len(self.Vz)-2,index_end_speed,2])
        
        x_result=1e3*self.Atoms_position[len(self.Vz)-2,index_end_speed,2]
        y_result=self.Atoms_speed[len(self.Vz)-2,index_end_speed,2]
        subplots_vels.scatter(x=1e3*self.Atoms_position[len(self.Vz)-2,index_end_speed,2],y=self.Atoms_speed[len(self.Vz)-2,index_end_speed,2], 
                     marker='x',  
                     s=300,       
                     color='red',  
                     linewidth=1,  
                     zorder=20)    

        if y_result > np.max(self.Atoms_speed/2):
            p=-1.5*(self.Vz[-1]-self.Vz[-2])
        else:
            p=0.75*(self.Vz[-1]-self.Vz[-2])
        subplots_vels.text(x=x_result-self.LZ*100,y=y_result+p,
                                s='  @ X-mark distance,\n atoms born @ '+str(self.Vz[-2])+' m/s: \n have speed of ' + str(np.round(self.Atoms_speed[len(self.Vz)-2, index_end_speed, 2], 1)) + ' m/s ', color='red')
        subplots_vels.set_ylabel('Atoms Speed (m/s)',ha='center',va='center')
        subplots_vels.set_xlabel('Z-Distance (mm)')
        subplots_vels.axvline(x=0, linestyle='dashed', color='gray', linewidth=1, zorder=1)
        subplots_vels.axvline(x=round(self.LZ * 1000), linestyle='dashed', color='gray', linewidth=1, zorder=1)
        subplots_vels.legend(loc='upper right', ncols=int(len(self.Vz)/3))
        if np.min(self.Atoms_speed[len(self.Vz)-2,index_end_speed,2]) > 0:
            subplots_vels.set_xlim([1e3*self.Atoms_position[0, 0, 2], round(1.40 * 1000 * self.LZ)])
        else:
            subplots_vels.set_xlim([1e3*self.Atoms_position[0, 0, 2], round(1.40 * 1000 * self.LZ)])
        y2_axis = self.fig_vels.axes[0].twinx()
        y2_axis.plot(1000 * self.z_axis_full[:, 2], self.By_ideal_full, linestyle='dashed', alpha=0.5, label='Bz_ideal',linewidth=0.5)
        y2_axis.plot(1000 * self.z_axis_full[:, 2], B, alpha=0.5, color='gray', label='Bz_MagnetsGenerated',linewidth=0.5)
        y2_axis.plot(1000 * self.z_axis_full[:, 2], -B, alpha=0.5, color='gray',linewidth=0.5)
        
        
        # Limits calculations
        # Max and min values of speed
        try:
            min_speed_position=np.argmin(self.Atoms_speed[:,:,2])
            print(min_speed_position)
            position = np.unravel_index(min_speed_position, self.Atoms_speed[:,:,2].shape)
            pos=np.int(position[0])
            out_of_xlim_list=np.where(self.Atoms_position[pos,:,2]<self.atoms_initial_z_position)
            print(out_of_xlim_list)
            out_of_xlim_index=out_of_xlim_list[0]
        except:
            out_of_xlim_index=END
        print(out_of_xlim_index)
        y1_max=np.max(self.Atoms_speed[:,:END,2])
        y1_min=np.min(self.Atoms_speed[:,:out_of_xlim_index,2])
        # Additional margin and graph limits
        y1_margin=(y1_max-y1_min)/20
        print('y1Max min margin',y1_max, y1_min, y1_margin)
        y1_lim_top=y1_max+2*y1_margin #Top limit y1
        y1_lim_bottom=y1_min-y1_margin #Bottom limit y1
        y1_range=y1_lim_top-y1_lim_bottom
       
        # Looking for values of V_cap at positions 0 & LZ
        y1_top_list=np.where(self.Atoms_position[len(self.Vz)-2,:,2]>0)
        y1_top_index=y1_top_list[0][0]
        y1_bottom_list=np.where(self.Atoms_position[len(self.Vz)-2,:,2]>self.LZ)
        y1_bottom_index=y1_bottom_list[0][0]
        y1_top=self.Atoms_speed[len(self.Vz)-2,y1_top_index,2]
        y1_bottom=self.Atoms_speed[len(self.Vz)-2,y1_bottom_index,2]
        y1_subrange=y1_top-y1_bottom
        offset_y1=(y1_lim_top-y1_top)/y1_range
       
        #Proportion window height Vs max_min speeds
        prop_range_subrange= y1_range/y1_subrange

        
        # Max and min values of B field
        y2_top=-self.By_current_full[self.B_points_additional]
        y2_bottom=-self.By_current_full[self.B_points_additional+self.B_points]
        print('y2 axis',y2_top-y2_bottom)
        # Additional margin and graph limits
        y2_subrange=y2_top-y2_bottom
        y2_range=y2_subrange*prop_range_subrange
        
        y2_lim_top=y2_top+y2_range*offset_y1
        y2_lim_bottom=y2_lim_top-y2_range
        
        # Impose calculated limits to match B and velocities slope
        subplots_vels.set_ylim([y1_lim_bottom,y1_lim_top])
        print('Vels lims', [y1_lim_bottom,y1_lim_top])
        print('Vels bottom top', [y1_bottom,y1_top])
        y2_axis.set_ylim([y2_lim_bottom,y2_lim_top])
        print('B bottom top',[y2_bottom,y2_top])
        print('B lims',[y2_lim_bottom,y2_lim_top])
        
        y2_axis.set_ylabel('Magnetic Field (mT)', color='grey')
        y2_axis.legend(loc='upper left', ncols=1)

        self.fig_vels.show()
        if self.test==True: print('<<-- FINISHED Zeeman Core atomic_kinetics()')
    
    def current_B(self):
        '''
            Calculates B with the actual position of magnets
        '''
        if self.test==True: print('-->>Entering Zeeman Core current_B()')
        self.By_current = self.col.getB(self.z_axis*1000)[:,1]
        self.By_current_full = self.col.getB(self.z_axis_full*1000)[:,1]
        if self.test==True: print('<<-- FINISHED Zeeman Core current_B()')
        