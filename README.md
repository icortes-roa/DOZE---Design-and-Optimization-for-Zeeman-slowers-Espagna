# DOZE: Design & Optimization for Zeeman slowers

The **Real Instituto y Observatorio de la Armada (ROA)** is the official authority responsible for the realization, maintenance, and dissemination of the SI second in Spain.

In our pursuit of developing an optical atomic clock, we have created **DOZE**, a tool designed to assist the scientific community in the design and simulation of Zeeman slowers using permanent magnets.

## Overview

DOZE allows users to perform comprehensive calculations regarding the slowing of atomic beams via the Zeeman effect. Specifically, it uses cylinder-shaped permanent magnets to generate the required magnetic field profiles.

## Key Features

DOZE includes the following functionalities:

* **Field Calculation:** Calculates the ideal magnetic field profile required to slow **$^{87}\text{Sr}$** or **$^{171}\text{Yb}$** atoms based on specific parameters (laser power, detuning, capture velocity, and final velocity).
* **Manual Optimization:** Allows the user to manually adjust magnet positions to observe how the generated magnetic field compares to the ideal profile in real-time.
* **Automatic Optimization:** Features an algorithm to automatically position magnets, approximating the ideal field as closely as possible.
* **Kinetic Simulations:** Runs calculations to simulate atomic kinetics along the slower.
* **Data Visualization:** Displays dynamic graphics related to the calculations and magnetic configurations.
* **Data Management:** Saves simulation data and plots in **HDF5** format within dated folders for organized archiving. It also allows loading previously saved data to resume analysis.

## Documentation

We encourage interested users to read the **User Manual** (included in this repository) to understand the tool's design philosophy, usage instructions, and expected outputs.
