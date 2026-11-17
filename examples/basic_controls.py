"""Small standalone example showing the stable control import surface."""

import sys
from pathlib import Path

# Run from a clone without installing: use the package in ../src.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import vtk

from multipanel.controls import SliderWidget, TextWidget


renderer = vtk.vtkRenderer()
window = vtk.vtkRenderWindow()
window.AddRenderer(renderer)
window.SetSize(800, 500)
interactor = vtk.vtkRenderWindowInteractor()
interactor.SetRenderWindow(window)

label = TextWidget(
    renderer, interactor, text="Opacity", position=(40, 170), editable=False)
slider = SliderWidget(
    renderer,
    interactor,
    min_value=0.0,
    max_value=1.0,
    initial_value=0.5,
    title="Opacity",
    position=(40, 120),
    bar_length=240,
    callback=lambda *_: None,
)
slider.valueChanged.connect(lambda value: label.setText(f"Opacity: {value:.2f}"))

renderer.SetBackground(0.12, 0.13, 0.15)
window.Render()
interactor.Initialize()
interactor.Start()
