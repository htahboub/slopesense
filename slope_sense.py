from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QMessageBox,
    QLabel,
    QSpinBox,
)

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from geopy.distance import distance
import xml.etree.ElementTree as ET

import numpy as np
import time
import argparse
import sys
import os


class SlopeSense(QMainWindow):
    def __init__(self, gpx_file):
        super().__init__()

        # Initialize the window
        self.setWindowTitle("Elevation App")
        self.setGeometry(100, 100, 1100, 600)

        # Load the GPX file and extract data
        self.distances, self.elevation_data = self.extract_elevation_data(gpx_file)

        # Check if distance is too small because 100m is uselessly small
        if self.distances[-1] < 100:
            QMessageBox.warning(
                self,
                "Invalid GPX File",
                "Distance is too small. Please use a GPX file with a distance greater than 100 meters.",
            )
            sys.exit()

        # Create the figure and canvas for plotting
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.setCentralWidget(self.canvas)

        # Initialize selected points attribute
        self.selected_points = []
        self.preview_point = None

        # Initialize plot elements
        self.ax = self.figure.add_subplot(111)
        (self.elevation_line,) = self.ax.plot(self.distances, self.elevation_data)
        self.selected_points_scatter = None
        self.preview_point_scatter = None
        self.plot_elevation_data()

        # Connect the mouse events
        self.canvas.mpl_connect("button_press_event", self.on_canvas_click)
        self.canvas.mpl_connect("motion_notify_event", self.on_canvas_hover)

        # Create buttons
        self.summary_button = QPushButton("Generate Summary")
        self.summary_button.clicked.connect(self.generate_summary)

        self.undo_button = QPushButton("Undo")
        self.undo_button.clicked.connect(self.undo_last_point)

        self.local_extrema_button = QPushButton("Find Local Extrema")
        self.local_extrema_button.clicked.connect(self.find_local_extrema)

        # Create a layout and add the buttons and canvas
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.local_extrema_button, 1)
        button_layout.addWidget(self.summary_button, 3)
        button_layout.addWidget(self.undo_button, 1)

        main_layout = QVBoxLayout()
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.canvas)

        # Create a widget to hold the layout
        widget = QWidget()
        widget.setLayout(main_layout)

        # Set the central widget
        self.setCentralWidget(widget)

        # Create a label and text box for setting the window size
        self.window_size_label = QLabel("Minima Window Search Size (smaller = more points):")
        self.window_size_textbox = QSpinBox()
        self.window_size_textbox.setMaximum(1000)
        self.window_size_textbox.setValue(80)
        self.window_size_textbox.setFixedWidth(60)
        self.window_size_textbox.setAttribute(Qt.WA_MacShowFocusRect, False)

        # Create a layout for the window size
        window_size_layout = QHBoxLayout()
        window_size_layout.addWidget(self.window_size_label)
        window_size_layout.addWidget(self.window_size_textbox)

        # Add the window size layout to the main layout
        main_layout.addLayout(window_size_layout)

    def find_local_extrema(self):
        if len(self.elevation_data) < 3:
            return

        window_size = int(self.window_size_textbox.text())

        if window_size < 3:
            QMessageBox.warning(
                self,
                "Invalid Window Size",
                "Window size should be greater than or equal to 3.",
            )
            return

        window_length = window_size // 2
        local_extrema = []

        for i in range(window_length, len(self.elevation_data) - window_length):
            window = self.elevation_data[i - window_length : i + window_length + 1]
            max_value = max(window)
            min_value = min(window)

            if self.elevation_data[i] == max_value or self.elevation_data[i] == min_value:
                local_extrema.append((self.distances[i], self.elevation_data[i]))

        self.selected_points.append(local_extrema)

        self.plot_elevation_data()

    def undo_last_point(self):
        if self.selected_points:
            self.selected_points.pop()
            self.plot_elevation_data()

    def extract_elevation_data(self, gpx_file):
        tree = ET.parse(gpx_file)
        root = tree.getroot()

        # Namespace dictionary
        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}

        # Find all <ele> elements
        elevation_elements = root.findall(".//gpx:ele", ns)

        # Extract elevation data from elements
        elevation_data = [float(element.text) for element in elevation_elements]

        # Find all <trkpt> elements
        trkpt_elements = root.findall(".//gpx:trkpt", ns)

        # Calculate cumulative distance for each point
        distances = [0]
        for i in range(1, len(trkpt_elements)):
            point1 = trkpt_elements[i - 1]
            point2 = trkpt_elements[i]
            lat1 = float(point1.get("lat"))
            lon1 = float(point1.get("lon"))
            lat2 = float(point2.get("lat"))
            lon2 = float(point2.get("lon"))
            dist = distance((lat1, lon1), (lat2, lon2)).meters
            cumulative_dist = distances[i - 1] + dist
            distances.append(cumulative_dist)

        return distances, elevation_data

    def plot_elevation_data(self):
        self.ax.clear()
        (self.elevation_line,) = self.ax.plot(self.distances, self.elevation_data)
        self.ax.set_xlabel("Distance (m)")
        self.ax.set_ylabel("Elevation")
        self.ax.set_title("Elevation Data")

        # Plot selected points
        if self.selected_points:
            points = []
            for point in self.selected_points:
                if type(point) == list:
                    points.extend(point)
                elif type(point) == tuple:
                    points.append(point)
                else:
                    raise TypeError("Point must be a list or tuple")
            selected_distances, selected_elevations = zip(*points)
            if self.selected_points_scatter:
                self.selected_points_scatter.remove()
            self.selected_points_scatter = self.ax.scatter(
                selected_distances, selected_elevations, c="red"
            )

        # Plot preview point
        if self.preview_point:
            x, y = self.preview_point
            if self.preview_point_scatter:
                self.preview_point_scatter.remove()
            self.preview_point_scatter = self.ax.scatter(x, y, c="orange")

        self.canvas.draw_idle()

    def on_canvas_click(self, event):
        if event.button == 1:
            x = event.xdata
            y = event.ydata
            if x is not None and y is not None:
                closest_idx = self.find_closest_index(x)
                cx = self.distances[closest_idx]
                cy = self.elevation_data[closest_idx]
                # Check if the clicked coordinates are within a radius of a selected point
                remove_point = False
                tolerance = self.distances[-1]/300
                for point in self.selected_points:
                    if type(point) == list:
                        # Check if the clicked coordinates are within a radius of a selected point
                        for sub_point in point:
                            point_x, _ = sub_point
                            if abs(point_x - cx) <= tolerance:
                                # Clicked within the radius of a sub selected point, remove it
                                self.selected_points.remove(point)
                                point.remove(sub_point)
                                self.selected_points.append(point)
                                remove_point = True
                                break
                    elif type(point) == tuple:
                        point_x, _ = point
                        if abs(point_x - cx) <= tolerance:
                            # Clicked within the radius of a selected point, remove it
                            self.selected_points.remove(point)
                            remove_point = True
                            break
                if not remove_point:
                    # Add the clicked point to the selected points
                    self.selected_points.append((cx, cy))

            # Reset the preview point
            self.preview_point = None

            # Update the plot
            self.plot_elevation_data()

    def on_canvas_hover(self, event):
        if event.xdata is not None and event.ydata is not None:
            x = event.xdata
            y = event.ydata

            # Calculate the closest distance and elevation
            start_time = time.time()
            closest_distance = self.find_closest_distance(x)
            closest_elevation = self.find_closest_elevation(closest_distance)

            # Update the preview point if it has changed
            if self.preview_point != (closest_distance, closest_elevation):
                self.preview_point = (closest_distance, closest_elevation)
                self.plot_elevation_data()
        else:
            # Hide the preview point when the mouse is not inside the graph
            self.preview_point = None
            self.plot_elevation_data()

    def find_closest_distance(self, x):
        min_distance = abs(self.distances[0] - x)
        closest_distance = self.distances[0]
        for distance in self.distances[1:]:
            dist = abs(distance - x)
            if dist < min_distance:
                min_distance = dist
                closest_distance = distance
            else:
                break
        return closest_distance

    def find_closest_elevation(self, distance):
        closest_idx = self.distances.index(distance)
        return self.elevation_data[closest_idx]

    def find_closest_index(self, x):
        closest_idx = (np.abs(self.distances - x)).argmin()
        return closest_idx

    def generate_summary(self):
        if len(self.selected_points) < 1:
            return

        summary = ""
        total_distance = 0
        total_gradient = 0

        # Calculate the gradients for the segments
        segments = []

        # Make a sorted copy of the selected points
        points = []
        for point in self.selected_points:
            if type(point) == list:
                points.extend(point)
            elif type(point) == tuple:
                points.append(point)
            else:
                raise TypeError("Point must be a list or tuple")
        sorted_points = sorted(points, key=lambda x: x[0])

        # Handle the first point separately
        start_distance = 0
        start_elevation = self.elevation_data[0]  # Use the elevation data at the first point
        distance = sorted_points[0][0] - start_distance
        gradient = (sorted_points[0][1] - start_elevation) / distance if distance > 0 else 0.0
        segments.append((distance, gradient))
        total_distance += distance
        total_gradient += gradient

        # Handle the remaining points
        for i in range(len(sorted_points) - 1):
            start_distance = sorted_points[i][0]
            start_elevation = sorted_points[i][1]
            end_distance = sorted_points[i + 1][0]
            end_elevation = sorted_points[i + 1][1]
            distance = end_distance - start_distance
            if distance > 0:
                gradient = (end_elevation - start_elevation) / distance
            else:
                gradient = 0.0
            segments.append((distance, gradient))
            total_distance += distance
            total_gradient += gradient

        # Handle the last point separately
        start_distance = sorted_points[-1][0]
        start_elevation = sorted_points[-1][1]
        end_distance = self.distances[-1]
        end_elevation = self.elevation_data[-1]
        distance = end_distance - start_distance
        gradient = (end_elevation - start_elevation) / distance if distance > 0 else 0.0
        segments.append((distance, gradient))
        total_distance += distance
        total_gradient += gradient

        # Build the summary string
        summary = ""
        for i, segment in enumerate(segments):
            distance, gradient = segment
            if gradient >= 0:
                grade = f"+{gradient * 100:.1f}%"
            else:
                grade = f"{gradient * 100:.1f}%"
            summary += f"{i+1}) {distance/1000:.1f} km at {grade} grade\n"

        summary += f"\nTotal: {total_distance/1000:.1f} km and {total_gradient * 100:.1f}% grade"

        QMessageBox.information(self, "Summary", summary)


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Elevation App")
    parser.add_argument("gpx_file", help="Path to the GPX file")
    args = parser.parse_args()

    # Check if the GPX file exists
    gpx_file_path = args.gpx_file
    if not os.path.isfile(gpx_file_path):
        print(f"GPX file '{gpx_file_path}' does not exist.")
        sys.exit(1)

    # Create the application
    app = QApplication(sys.argv)
    window = SlopeSense(gpx_file_path)
    window.show()

    # Run the application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
