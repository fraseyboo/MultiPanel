"""Interactive chart demos (moved out of ``multipanel.charts``).

These use the functional helpers on raw VTK charts and the deprecated
chart actors (``add_chart_actor``, ``DraggableChartInteractorStyle``,
``install_chart_mode``), which warn. For the widget API see
``chart_panel_demo.py`` and ``chart_gallery.py``.

Requires the ``scientific`` extra. Run with ``python examples/chart_demos.py``.
"""
import numpy as np
import vtk

from multipanel.charts import (
    DraggableChartInteractorStyle,
    install_chart_mode,
    _determine_line_style,
    add_bar_chart,
    add_chart_actor,
    add_errorbar_plot,
    add_filled_area_chart,
    add_gridlines,
    add_label,
    add_legend,
    add_line_chart,
    add_scatter_chart,
    color_to_RGBA_255,
    figure,
    imshow,
    set_x_axis_limits,
    set_x_axis_title,
    set_y_axis_title,
    show,
)


def test_tree_heatmap_auto_collapse():
    """
    Demonstrates collapsing a tree heatmap to the two leaf nodes closest to the root.
    Returns:
        vtk.vtkRenderWindow: The render window containing the visualization.
    """
    graph = vtk.vtkMutableDirectedGraph()
    root = graph.AddVertex()
    internal_one = graph.AddChild(root)
    internal_two = graph.AddChild(internal_one)
    a = graph.AddChild(internal_two)
    b = graph.AddChild(internal_two)
    c = graph.AddChild(internal_one)

    weights = vtk.vtkDoubleArray()
    weights.SetNumberOfTuples(5)
    weights.SetValue(graph.GetEdgeId(root, internal_one), 1.0)
    weights.SetValue(graph.GetEdgeId(internal_one, internal_two), 2.0)
    weights.SetValue(graph.GetEdgeId(internal_two, a), 1.0)
    weights.SetValue(graph.GetEdgeId(internal_two, b), 1.0)
    weights.SetValue(graph.GetEdgeId(internal_one, c), 3.0)
    weights.SetName("weight")
    graph.GetEdgeData().AddArray(weights)

    names = vtk.vtkStringArray()
    names.SetNumberOfTuples(6)
    names.SetValue(a, "a")
    names.SetValue(b, "b")
    names.SetValue(c, "c")
    names.SetName("node name")
    graph.GetVertexData().AddArray(names)

    node_weights = vtk.vtkDoubleArray()
    node_weights.SetNumberOfTuples(6)
    node_weights.SetValue(root, 0.0)
    node_weights.SetValue(internal_one, 1.0)
    node_weights.SetValue(internal_two, 3.0)
    node_weights.SetValue(a, 4.0)
    node_weights.SetValue(b, 4.0)
    node_weights.SetValue(c, 4.0)
    node_weights.SetName("node weight")
    graph.GetVertexData().AddArray(node_weights)

    table = vtk.vtkTable()
    table_names = vtk.vtkStringArray()
    m1 = vtk.vtkDoubleArray()
    m2 = vtk.vtkDoubleArray()
    m3 = vtk.vtkDoubleArray()

    table_names.SetNumberOfTuples(3)
    table_names.SetValue(0, "c")
    table_names.SetValue(1, "b")
    table_names.SetValue(2, "a")
    table_names.SetName("name")

    m1.SetNumberOfTuples(3)
    m2.SetNumberOfTuples(3)
    m3.SetNumberOfTuples(3)

    m1.SetName("m1")
    m2.SetName("m2")
    m3.SetName("m3")

    m1.SetValue(0, 1.0)
    m1.SetValue(1, 3.0)
    m1.SetValue(2, 1.0)

    m2.SetValue(0, 2.0)
    m2.SetValue(1, 2.0)
    m2.SetValue(2, 2.0)

    m3.SetValue(0, 3.0)
    m3.SetValue(1, 1.0)
    m3.SetValue(2, 3.0)

    table.AddColumn(table_names)
    table.AddColumn(m1)
    table.AddColumn(m2)
    table.AddColumn(m3)

    actor = vtk.vtkContextActor()

    tree = vtk.vtkTree()
    tree.ShallowCopy(graph)

    tree_item = vtk.vtkTreeHeatmapItem()
    tree_item.SetTree(tree)
    tree_item.SetTable(table)
    tree_item.GetDendrogram().DisplayNumberOfCollapsedLeafNodesOff()

    trans = vtk.vtkContextTransform()
    trans.SetInteractive(True)
    trans.Translate(20, 30)
    trans.Scale(2.5, 2.5)
    trans.AddItem(tree_item)
    actor.GetScene().AddItem(trans)

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(1.0, 1.0, 1.0)

    render_window = vtk.vtkRenderWindow()
    render_window.SetSize(400, 200)
    render_window.AddRenderer(renderer)
    renderer.AddActor(actor)
    actor.GetScene().SetRenderer(renderer)

    interactor_style = vtk.vtkContextInteractorStyle()
    interactor_style.SetScene(actor.GetScene())

    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetInteractorStyle(interactor_style)
    interactor.SetRenderWindow(render_window)
    render_window.SetMultiSamples(0)
    render_window.Render()

    # Collapse to two leaf nodes closest to the root
    # tree_item.CollapseToNumberOfLeafNodes(2)

    # Optionally start interaction
    interactor.Initialize()
    interactor.Start()

    return render_window


def test_tanglegram_item():
    # tree #1
    """Verify tanglegram item."""
    graph1 = vtk.vtkMutableDirectedGraph()
    root = graph1.AddVertex()
    internal_one = graph1.AddChild(root)
    internal_two = graph1.AddChild(internal_one)
    a = graph1.AddChild(internal_two)
    b = graph1.AddChild(internal_two)
    c = graph1.AddChild(internal_one)

    weights = vtk.vtkDoubleArray()
    weights.SetNumberOfTuples(5)
    weights.SetValue(graph1.GetEdgeId(root, internal_one), 1.0)
    weights.SetValue(graph1.GetEdgeId(internal_one, internal_two), 2.0)
    weights.SetValue(graph1.GetEdgeId(internal_two, a), 1.0)
    weights.SetValue(graph1.GetEdgeId(internal_two, b), 1.0)
    weights.SetValue(graph1.GetEdgeId(internal_one, c), 3.0)
    weights.SetName("weight")
    graph1.GetEdgeData().AddArray(weights)

    names1 = vtk.vtkStringArray()
    names1.SetNumberOfTuples(6)
    names1.SetValue(a, "cat")
    names1.SetValue(b, "dog")
    names1.SetValue(c, "human")
    names1.SetName("node name")
    graph1.GetVertexData().AddArray(names1)

    node_weights = vtk.vtkDoubleArray()
    node_weights.SetNumberOfTuples(6)
    node_weights.SetValue(root, 0.0)
    node_weights.SetValue(internal_one, 1.0)
    node_weights.SetValue(internal_two, 3.0)
    node_weights.SetValue(a, 4.0)
    node_weights.SetValue(b, 4.0)
    node_weights.SetValue(c, 4.0)
    node_weights.SetName("node weight")
    graph1.GetVertexData().AddArray(node_weights)

    # tree #2
    graph2 = vtk.vtkMutableDirectedGraph()
    root2 = graph2.AddVertex()
    internal_one2 = graph2.AddChild(root2)
    internal_two2 = graph2.AddChild(internal_one2)
    a2 = graph2.AddChild(internal_two2)
    b2 = graph2.AddChild(internal_two2)
    c2 = graph2.AddChild(internal_one2)

    weights2 = vtk.vtkDoubleArray()
    weights2.DeepCopy(weights)
    weights2.SetName("weight")
    graph2.GetEdgeData().AddArray(weights2)

    names2 = vtk.vtkStringArray()
    names2.SetNumberOfTuples(6)
    names2.SetValue(a2, "dog food")
    names2.SetValue(b2, "cat food")
    names2.SetValue(c2, "steak")
    names2.SetName("node name")
    graph2.GetVertexData().AddArray(names2)

    node_weights2 = vtk.vtkDoubleArray()
    node_weights2.DeepCopy(node_weights)
    node_weights2.SetName("node weight")
    graph2.GetVertexData().AddArray(node_weights2)

    # set up correspondence table: who eats what
    table = vtk.vtkTable()
    eaters = vtk.vtkStringArray()
    hunger_for_steak = vtk.vtkDoubleArray()
    hunger_for_steak.SetName("steak")
    hunger_for_dog_food = vtk.vtkDoubleArray()
    hunger_for_dog_food.SetName("dog food")
    hunger_for_cat_food = vtk.vtkDoubleArray()
    hunger_for_cat_food.SetName("cat food")

    eaters.SetNumberOfTuples(3)
    hunger_for_steak.SetNumberOfTuples(3)
    hunger_for_dog_food.SetNumberOfTuples(3)
    hunger_for_cat_food.SetNumberOfTuples(3)

    eaters.SetValue(0, "human")
    eaters.SetValue(1, "dog")
    eaters.SetValue(2, "cat")

    hunger_for_steak.SetValue(0, 2.0)
    hunger_for_steak.SetValue(1, 1.0)
    hunger_for_steak.SetValue(2, 1.0)

    hunger_for_dog_food.SetValue(0, 0.0)
    hunger_for_dog_food.SetValue(1, 2.0)
    hunger_for_dog_food.SetValue(2, 0.0)

    hunger_for_cat_food.SetValue(0, 0.0)
    hunger_for_cat_food.SetValue(1, 1.0)
    hunger_for_cat_food.SetValue(2, 2.0)

    table.AddColumn(eaters)
    table.AddColumn(hunger_for_steak)
    table.AddColumn(hunger_for_dog_food)
    table.AddColumn(hunger_for_cat_food)

    actor = vtk.vtkContextActor()

    tree1 = vtk.vtkTree()
    tree1.ShallowCopy(graph1)

    tree2 = vtk.vtkTree()
    tree2.ShallowCopy(graph2)

    tanglegram = vtk.vtkTanglegramItem()
    tanglegram.SetTree1(tree1)
    tanglegram.SetTree2(tree2)
    tanglegram.SetTable(table)
    tanglegram.SetTree1Label("Diners")
    tanglegram.SetTree2Label("Meals")

    trans = vtk.vtkContextTransform()
    trans.SetInteractive(True)
    trans.AddItem(tanglegram)
    # center the item within the render window
    trans.Translate(20, 75)
    trans.Scale(1.25, 1.25)
    actor.GetScene().AddItem(trans)

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(1.0, 1.0, 1.0)

    render_window = vtk.vtkRenderWindow()
    render_window.SetSize(400, 200)
    render_window.AddRenderer(renderer)
    renderer.AddActor(actor)
    actor.GetScene().SetRenderer(renderer)

    interactor_style = vtk.vtkContextInteractorStyle()
    interactor_style.SetScene(actor.GetScene())

    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetInteractorStyle(interactor_style)
    interactor.SetRenderWindow(render_window)
    render_window.SetMultiSamples(0)
    render_window.Render()

    # If you want to interact, uncomment below:
    interactor.Initialize()
    interactor.Start()


def generate_test_data(num_points=50):
    """
    Generate a vtkTable containing test data for visualization.
    The table includes columns for X-axis values, cosine, sine, sine with an offset,
    and tangent values. The data is generated based on the specified number of points.
    Parameters:
        num_points (int): The number of data points to generate. Default is 50.
    Returns:
        vtk.vtkTable: A table containing the generated test data with the following
        columns:
            - "X Axis": X-axis values.
            - "Cosine": Cosine values of the X-axis.
            - "Sine": Sine values of the X-axis.
            - "Sine2": Sine values of the X-axis with an offset of 0.5.
            - "Tangent": Tangent values of the X-axis.
    """

    # Create a table with some points in it
    table = vtk.vtkTable()
    arrX = vtk.vtkFloatArray()
    arrX.SetName("X Axis")
    table.AddColumn(arrX)

    arrC = vtk.vtkFloatArray()
    arrC.SetName("Cosine")
    table.AddColumn(arrC)

    arrS = vtk.vtkFloatArray()
    arrS.SetName("Sine")
    table.AddColumn(arrS)

    arrS2 = vtk.vtkFloatArray()
    arrS2.SetName("Sine2")
    table.AddColumn(arrS2)

    tangent = vtk.vtkFloatArray()
    tangent.SetName("Tangent")
    table.AddColumn(tangent)

    inc = 7.5 / (num_points - 1)
    table.SetNumberOfRows(num_points)
    for i in range(num_points):
        table.SetValue(i, 0, i * inc)
        table.SetValue(i, 1, np.cos(i * inc))
        table.SetValue(i, 2, np.sin(i * inc))
        table.SetValue(i, 3, np.sin(i * inc) + 0.5)
        table.SetValue(i, 4, np.clip(np.tan(i * inc), -10, 10))

    return table


def mpl_style_example():
    """
    Demonstrates the creation of various charts using a VTK-based charting library.

    Designed to operate similarly to matplotlib, this function generates a figure with
    multiple chart types, including filled area charts, line charts, and scatter charts.

    The figure is styled with a specific size, title, and background color.
    Charts included:
    - Filled area chart: Displays a shaded area between two data series.
    - Line charts: Plots two dashed red lines based on test data.
    - Scatter chart: Plots red scatter points with a specific marker style.
    The function also includes commented-out examples for additional chart types such as
    box plots, pie charts, and bar charts.
    Note:
    - The function relies on external helper functions like `generate_test_data`,
      `add_filled_area_chart`, `add_line_chart`, and `add_scatter_chart`.
    - The `show` function is used to render the figure.
    Parameters:
    None
    Returns:
    None
    """

    table = generate_test_data()

    fig = figure(fig_size=(1280, 1024), title="VTK Chart", background_color="white")

    # add_box_plot(figure=fig)

    # pie_values = [1, 2, 3, 4]
    # pie_labels = ["A", "B", "C", "D"]

    # add_pie_chart(figure=fig, values=pie_values, labels=pie_labels)

    size = (100, 100)  # Dimensions of the array
    center = (75, 50)  # Center of the Gaussian
    sigma = 10  # Standard deviation
    y, x = np.meshgrid(np.arange(size[0]), np.arange(size[1]), indexing="ij")
    gaussian = np.exp(-((x - center[1]) ** 2 + (y - center[0]) ** 2) / (2 * sigma**2))

    # Visualize the Gaussian spot using imshow
    imshow(gaussian, figure=fig, extent=(0, 7.5, -10, 10), colormap="viridis")

    add_scatter_chart(
        x=(np.random.rand(100) * 7.5),
        y=(np.random.rand(100) * 20) - 10,
        figure=fig,
        gridlines_color=None,
        marker_size=10,
        color="red",
        marker_style="x",
    )

    add_bar_chart(x=table.GetColumn(0), y=table.GetColumn(4), figure=fig)

    add_filled_area_chart(
        x=table.GetColumn(0),
        y_lower=table.GetColumn(2),
        y_upper=table.GetColumn(3),
        figure=fig,
        color="steel_blue",
        opacity=0.5,
    )
    add_line_chart(
        x=table.GetColumn(0),
        y=table.GetColumn(1),
        figure=fig,
        color="red",
        line_style="dashed",
    )
    add_line_chart(
        x=table.GetColumn(0),
        y=table.GetColumn(2),
        figure=fig,
        color="red",
        line_style="dashed",
    )
    add_scatter_chart(
        x=table.GetColumn(0),
        y=table.GetColumn(3),
        figure=fig,
        gridlines_color="Black",
        marker_size=5,
        marker_style="x",
        color="red",
    )

    # surf = add_xyz_suface_plot(figure=fig)

    # add_errorbar_plot(
    #     x=table.GetColumn(0),
    #     y=table.GetColumn(1),
    #     y_errors=np.random.rand(50, 2),
    #     x_errors=np.random.rand(50, 2) / 8,
    #     figure=fig,
    #     error_width=0.1,
    # )


    # add_dendrogram(
    #     figure=fig,
    #     tree=None,
    # )

    set_x_axis_title(fig.GetScene().GetItem(0), "X Axis", font_size=20, color="black")
    set_x_axis_limits(fig, 0, 7.5, forced=True)

    link = fig.GetScene().GetAnnotationLink()
    print("Link", link, sorted(dir(link)))

    scene = fig.GetScene()
    print("Scene", scene, sorted(dir(scene)))

    total_items = scene.GetNumberOfItems()
    print("Total items", total_items)

    # for i in range(total_items):
    #     item = scene.GetItem(i)
    #     if isinstance(item, vtk.vtkChartXY):
    #         print('Item is vtkChartXY')
    #         print("Item", item, sorted(dir(item)))
    #         link = item.GetAnnotationLink()
    #         print("Link", link, sorted(dir(link)))
    #         number_of_plots = item.GetNumberOfPlots()
    #         print("Number of plots", number_of_plots)
    #         for j in range(number_of_plots):
    #             plot_item = item.GetPlot(j)
    #             plot_item.SetInteractive(False)
    #             print("Plot item", plot_item, sorted(dir(plot_item)))
    #             if hasattr(plot_item, "GetTooltip"):
    #                 tooltip = plot_item.GetTooltip()
    #                 print("Tooltip", tooltip, sorted(dir(tooltip)))
    #             else:
    #                 print("Plot item does not have GetTooltip")
    #             if hasattr(plot_item, "GetAnnotationLink"):
                   
    #                 link = plot_item.GetAnnotationLink()
    #                 print("Plot item", plot_item, sorted(dir(plot_item)))
    #                 print("Link", link, sorted(dir(link)))
    #             else:
    #                 # print("Plot item", plot_item, sorted(dir(plot_item)))
    #                 print("Plot item does not have GetAnnotationLink")
  
    #     else:
    #         print("Item is not vtkChartXY")
    #         link = item.GetAnnotationLink()
    #         print("Link", link, sorted(dir(link)))


    show(fig)

    for i in range(total_items):
        item = scene.GetItem(i)
        if isinstance(item, vtk.vtkChartXY):
            print(f"Item {i} is vtkChartXY")
            link = item.GetAnnotationLink()
            if link is not None:
                print(f"Annotation link for item {i}: {link}")
            else:
                print(f"No annotation link for item {i}")
            number_of_plots = item.GetNumberOfPlots()
            for j in range(number_of_plots):
                plot_item = item.GetPlot(j)
                link = plot_item.GetAnnotationLink() if hasattr(plot_item, "GetAnnotationLink") else None
                if link is not None:
                    print(f"Annotation link for plot {j} in item {i}: {link}")
                else:
                    print(f"No annotation link for plot {j} in item {i}")
        else:
            print(f"Item {i} is not vtkChartXY")
            link = item.GetAnnotationLink() if hasattr(item, "GetAnnotationLink") else None
            if link is not None:
                print(f"Annotation link for item {i}: {link}")
            else:
                print(f"No annotation link for item {i}")


def test_plots():
    """
    Generates a test visualization using VTK charts and plots.
    This function creates a 2x2 chart matrix and populates it with various types
    of plots, including scatter plots, filled area charts, bar charts, and line
    charts. It uses test data generated by `generate_test_data()` and displays
    the resulting visualization in an interactive VTK render window.
    The following types of charts are added to the matrix:
    - Scatter chart
    - Filled area chart
    - Bar chart
    - Line charts with different styles and colors
    - A legend for the line charts
    The layout of the chart matrix is configured with custom gutter spacing and
    borders.
    Note:
        This function requires VTK and NumPy libraries to be installed.
    Dependencies:
        - VTK (Visualization Toolkit)
        - NumPy
    Returns:
        None
    """

    table = generate_test_data()

    figure = vtk.vtkContextView()
    figure.GetRenderWindow().SetSize(1280, 1024)
    figure.GetRenderWindow().SetWindowName("ChartMatrix")

    matrix = vtk.vtkChartMatrix()
    figure.GetScene().AddItem(matrix)
    matrix.SetSize(vtk.vtkVector2i(2, 2))
    matrix.SetGutter(vtk.vtkVector2f(90.0, 90.0))
    matrix.SetBorders(100, 50, 50, 50)

    # add_scatter_chart(random_points, axes=matrix.GetChart(vtk.vtkVector2i(0, 0)))

    # add_box_plot(axes=matrix.GetChart(vtk.vtkVector2i(0, 0)), figure=figure)

    add_scatter_chart(
        x=table.GetColumn(0),
        y=table.GetColumn(3),
        axes=matrix.GetChart(vtk.vtkVector2i(0, 1)),
    )

    add_filled_area_chart(
        x=table.GetColumn(0),
        y_lower=table.GetColumn(1),
        y_upper=table.GetColumn(2),
        axes=matrix.GetChart(vtk.vtkVector2i(0, 1)),
    )

    add_bar_chart(
        x=table.GetColumn(0),
        y=table.GetColumn(4),
        axes=matrix.GetChart(vtk.vtkVector2i(1, 1)),
    )

    add_scatter_chart(
        x=table.GetColumn(0),
        y=table.GetColumn(3),
        axes=matrix.GetChart(vtk.vtkVector2i(1, 1)),
    )

    add_line_chart(
        x=table.GetColumn(0),
        y=table.GetColumn(1),
        axes=matrix.GetChart(vtk.vtkVector2i(1, 0)),
        color="red",
        line_style="dashed",
    )

    add_line_chart(
        x=table.GetColumn(0),
        y=table.GetColumn(2),
        axes=matrix.GetChart(vtk.vtkVector2i(1, 0)),
        color="blue",
        line_style="solid",
    )

    add_errorbar_plot(
        x=table.GetColumn(0),
        y=table.GetColumn(2),
        y_errors=0.2,
        x_errors=0.05,
        axes=matrix.GetChart(vtk.vtkVector2i(1, 0)),
        error_width=0.1,
        line_thickness=1,
        line_color="purple",
    )

    # add_dendrogram(figure=figure)


    # add_label(figure=figure, label="Test label")


    add_legend(matrix.GetChart(vtk.vtkVector2i(1, 0)))
    add_legend(matrix.GetChart(vtk.vtkVector2i(0, 1)))
    add_legend(matrix.GetChart(vtk.vtkVector2i(1, 1)))

    figure.GetRenderWindow().Render()
    figure.GetInteractor().Initialize()
    figure.GetInteractor().Start()


def test_block():
    """Verify block."""
    fig = figure(fig_size=(800, 600), title="VTK Chart", background_color="grey")

    add_label(figure=fig, label="TEST LABEL")

    show(fig)


def test_in_vtk_render_window():
    """Verify in vtk render window."""
    table = generate_test_data()

    fig = figure(fig_size=(800, 600), title="VTK Chart in Render Window", background_color="white")

    add_line_chart(
        x=table.GetColumn(0),
        y=table.GetColumn(1),
        figure=fig,
        color="blue",
        line_style="solid",
    )

    # Now embed the figure's render window into a new render window
    render_window = vtk.vtkRenderWindow()
    render_window.SetSize(800, 600)
    render_window.SetWindowName("Embedded VTK Chart")

    renderer = vtk.vtkRenderer()
    render_window.AddRenderer(renderer)

    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(render_window)
    interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())

    # Create a vtkContextActor to hold the figure's scene
    context_actor = vtk.vtkContextActor()
    context_actor.SetScene(fig.GetScene())

    test_sphere = vtk.vtkSphereSource()
    test_sphere.SetRadius(50)
    test_sphere.SetThetaResolution(30)
    test_sphere.SetPhiResolution(30)
    test_sphere.Update()
    sphere_mapper = vtk.vtkPolyDataMapper()
    sphere_mapper.SetInputConnection(test_sphere.GetOutputPort())
    sphere_actor = vtk.vtkActor()
    sphere_actor.SetMapper(sphere_mapper)
    sphere_actor.SetPosition(400, 300, 0)


    renderer.AddActor(context_actor)
    renderer.AddActor(sphere_actor)
    renderer.SetBackground(1.0, 1.0, 1.0)

    render_window.Render()
    interactor.Initialize()
    interactor.Start()


def test_in_vtk_render_window_separate():
    # --- Main Render Window + Interactor ---
    """Verify in vtk render window separate."""
    ren_win = vtk.vtkRenderWindow()
    iren = vtk.vtkRenderWindowInteractor()
    iren.SetRenderWindow(ren_win)

    # --- 3D renderer ---
    ren3d = vtk.vtkRenderer()
    ren_win.AddRenderer(ren3d)
    ren3d.SetBackground(0.1, 0.2, 0.4)

    # Example 3D object
    sphere = vtk.vtkSphereSource()
    sphere.Update()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(sphere.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    ren3d.AddActor(actor)

    # --- 2D Chart renderer ---
    renChart = vtk.vtkRenderer()
    renChart.SetLayer(1)     # Put above 3D
    ren3d.SetLayer(0)
    ren_win.SetNumberOfLayers(2)
    renChart.SetBackgroundAlpha(1)  # Transparent overlay

    ren_win.AddRenderer(renChart)

    # --- vtkContext scene for chart ---
    chartScene = vtk.vtkContextScene()
    chartScene.SetRenderer(renChart)

    # Chart object (same as in vtkContextView)
    chart = vtk.vtkChartXY()

    table = generate_test_data()


    line_chart = chart.AddPlot(vtk.vtkChart.LINE)
    line_chart.SetInputData(table, 0, 1)
    line_chart.SetColor(*color_to_RGBA_255("blue"))
    line_chart.SetWidth(2)
    line_chart.GetPen().SetLineType(_determine_line_style('solid'))
    line_chart.SetOpacity(1)


    # table = generate_test_data()

    # fig = figure(fig_size=(800, 600), title="VTK Chart in Render Window", background_color="white")

    # add_line_chart(
    #     x=table.GetColumn(0),
    #     y=table.GetColumn(1),
    #     figure=chartScene,
    #     color="blue",
    #     line_style="solid",
    # )

    # chartScene.AddItem(chart)

    # --- Use vtkContextInteractorStyle (important!) ---
    chartInteractor = vtk.vtkContextInteractorStyle()
    iren.SetInteractorStyle(chartInteractor)
    chartInteractor.SetScene(chartScene)

    iren.Initialize()
    ren_win.Render()
    iren.Start()


def test_in_vtk_render_window_3():

    # --- Render window and interactor ---
    """Verify in vtk render window 3."""
    ren_win = vtk.vtkRenderWindow()
    ren_win.SetSize(800, 600)

    iren = vtk.vtkRenderWindowInteractor()
    iren.SetRenderWindow(ren_win)

    # ===========================================================
    # =============== 3D RENDERER (layer 0) ======================
    # ===========================================================
    ren3d = vtk.vtkRenderer()
    ren3d.SetBackground(0.1, 0.2, 0.4)
    ren3d.SetLayer(0)

    ren_win.AddRenderer(ren3d)

    # Example 3D object
    sphere = vtk.vtkSphereSource()
    sphere.Update()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(sphere.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    ren3d.AddActor(actor)


    # ===========================================================
    # =============== CHART RENDERER (layer 1) ===================
    # ===========================================================
    renCharts = vtk.vtkRenderer()
    renCharts.SetLayer(1)
    renCharts.SetBackgroundAlpha(0.6)  # transparent
    ren_win.SetNumberOfLayers(2)
    ren_win.AddRenderer(renCharts)

    # Context scene that holds all charts
    scene = vtk.vtkContextScene()
    scene.SetRenderer(renCharts)

    contextActor = vtk.vtkContextActor()
    contextActor.SetScene(scene)
    renCharts.AddActor(contextActor)


    # ===========================================================
    # =============== CREATE A TABLE UTILITY =====================
    # ===========================================================
    def make_table():
        """Create table."""
        import numpy as np
        x = vtk.vtkFloatArray()
        y = vtk.vtkFloatArray()
        x.SetName("X")
        y.SetName("Y")

        for i in range(50):
            x.InsertNextValue(i)
            y.InsertNextValue(np.sin(i * 0.2))

        table = vtk.vtkTable()
        table.AddColumn(x)
        table.AddColumn(y)

        return table


    # ===========================================================
    # =============== CREATE MULTIPLE CHARTS =====================
    # ===========================================================

    # Chart 1 (top-left)
    chart1 = vtk.vtkChartXY()
    # chart1.SetGeometry(vtk.vtkRectf(20, 300, 350, 250))  # x, y, w, h
    x, y, w, h = 20, 300, 350, 250
    chart1.SetPoint1([x, y])          # bottom-left
    chart1.SetPoint2([x + w, y + h])  # top-right
    table1 = make_table()
    plot1 = chart1.AddPlot(vtk.vtkChart.LINE)
    plot1.SetInputData(table1, 0, 1)
    scene.AddItem(chart1)

    # Chart 2 (bottom-right)
    chart2 = vtk.vtkChartXY()
    # chart2.SetGeometry(vtk.vtkRectf(430, 20, 350, 250))
    x, y, w, h = 430, 20, 350, 250
    chart2.SetPoint1([x, y])
    chart2.SetPoint2([x + w, y + h])
    table2 = make_table()
    plot2 = chart2.AddPlot(vtk.vtkChart.LINE)
    plot2.SetInputData(table2, 0, 1)
    scene.AddItem(chart2)


    # ===========================================================
    # =============== INTERACTOR STYLE ===========================
    # ===========================================================

    # This gives full chart zoom/pan/select behavior
    style = vtk.vtkContextInteractorStyle()
    style.SetScene(scene)
    iren.SetInteractorStyle(style)


    # ===========================================================
    # ===================== START ===============================
    # ===========================================================

    iren.Initialize()

    ren_win.Render()
    iren.Start()


def test_draggable_charts():


    # --- Render window and interactor ---
    """Verify draggable charts."""
    ren_win = vtk.vtkRenderWindow()
    ren_win.SetSize(800, 600)
    iren = vtk.vtkRenderWindowInteractor()
    iren.SetRenderWindow(ren_win)

    # --- 3D Renderer ---
    ren3d = vtk.vtkRenderer()
    ren3d.SetLayer(0)
    ren3d.SetBackground(0.1, 0.2, 0.4)
    ren_win.AddRenderer(ren3d)

    # Example 3D object
    sphere = vtk.vtkSphereSource()
    sphere.Update()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(sphere.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    ren3d.AddActor(actor)

    # --- 2D Chart Renderer (overlay) ---
    renCharts = vtk.vtkRenderer()
    renCharts.SetLayer(1)
    renCharts.SetBackgroundAlpha(0)
    ren_win.SetNumberOfLayers(2)
    ren_win.AddRenderer(renCharts)

    # --- Utility to make sample table ---
    def make_table():
        """Create table."""
        x = vtk.vtkFloatArray()
        y = vtk.vtkFloatArray()
        x.SetName("X")
        y.SetName("Y")
        for i in range(50):
            x.InsertNextValue(i)
            y.InsertNextValue(np.sin(i * 0.2))
        table = vtk.vtkTable()
        table.AddColumn(x)
        table.AddColumn(y)
        return table

    # --- Context scene and actor ---
    scene = vtk.vtkContextScene()
    scene.SetRenderer(renCharts)
    contextActor = vtk.vtkContextActor()
    contextActor.SetScene(scene)
    contextActor.SetUseBounds(True)
    contextActor.SetDragable(True)
    renCharts.AddActor(contextActor)

    # --- Create two charts ---
    charts = []

    def create_chart(x, y, w, h):
        """Create chart."""
        chart = vtk.vtkChartXY()
        chart.SetPoint1([x, y])
        chart.SetPoint2([x + w, y + h])
        table = make_table()
        plot = chart.AddPlot(vtk.vtkChart.LINE)
        plot.SetInputData(table, 0, 1)
        scene.AddItem(chart)
        charts.append(chart)
        return chart

    chart1 = create_chart(20, 300, 50, 50)
    # chart2 = create_chart(430, 20, 350, 250)

    # --- Custom interactor style for dragging/resizing charts ---
    class DraggableChartStyle(vtk.vtkContextInteractorStyle):
        def __init__(self):
            """Initialize the instance."""
            super().__init__()
            self.dragging = False
            self.resizing = False
            self.active_chart = None
            self.drag_offset = [0, 0]
            self.resize_corner_size = 10

            self.AddObserver("LeftButtonPressEvent", self.OnLeftButtonDown)
            self.AddObserver("MouseMoveEvent", self.OnMouseMove)
            self.AddObserver("LeftButtonReleaseEvent", self.OnLeftButtonUp)


        def OnLeftButtonDown(self, obj, event):
            """Execute the on left button down operation."""
            pos = self.GetInteractor().GetEventPosition()
            # Check if we clicked on a chart
            print("Click at", pos)
            for chart in charts[::-1]:  # topmost first
                x0, y0 = chart.GetPoint1()
                x1, y1 = chart.GetPoint2()
                if x0 <= pos[0] <= x1 and y0 <= pos[1] <= y1:
                    # Check corner for resizing
                    if (x1 - self.resize_corner_size <= pos[0] <= x1 and
                        y0 <= pos[1] <= y0 + self.resize_corner_size):
                        self.resizing = True
                    else:
                        self.dragging = True
                        self.drag_offset = [pos[0] - x0, pos[1] - y0]
                    self.active_chart = chart
                    break
            super().OnLeftButtonDown()

        def OnMouseMove(self, obj, event):
            """Execute the on mouse move operation."""
            if self.dragging or self.resizing:
                pos = self.GetInteractor().GetEventPosition()
                chart = self.active_chart
                x0, y0 = chart.GetPoint1()
                x1, y1 = chart.GetPoint2()
                w, h = x1 - x0, y1 - y0
                if self.dragging:
                    new_x0 = pos[0] - self.drag_offset[0]
                    new_y0 = pos[1] - self.drag_offset[1]
                    chart.SetPoint1([new_x0, new_y0])
                    chart.SetPoint2([new_x0 + w, new_y0 + h])
                elif self.resizing:
                    chart.SetPoint2([pos[0], pos[1]])
                self.GetInteractor().GetRenderWindow().Render()
            else:
                super().OnMouseMove()

        def OnLeftButtonUp(self, obj, event):
            """Execute the on left button up operation."""
            self.dragging = False
            self.resizing = False
            self.active_chart = None
            super().OnLeftButtonUp()

    # --- Use the custom style ---
    style = DraggableChartStyle()
    style.SetScene(scene)
    iren.SetInteractorStyle(style)

    # --- Start ---
    iren.Initialize()
    ren_win.Render()
    iren.Start()


def test_chart_actor():

    # --- Render window and interactor ---

    """Verify chart actor."""
    ren_win = vtk.vtkRenderWindow()
    ren_win.SetSize(800, 600)

    ren2d = vtk.vtkRenderer()
    ren2d.SetLayer(1)
    ren2d.SetBackgroundAlpha(0)  # transparent
    ren_win.SetNumberOfLayers(2)
    ren_win.AddRenderer(ren2d)



    ren3d = vtk.vtkRenderer()
    ren3d.SetLayer(0)
    ren3d.SetBackground(0.1, 0.2, 0.4)
    ren_win.AddRenderer(ren3d)

    iren = vtk.vtkRenderWindowInteractor()
    iren.SetRenderWindow(ren_win)
    # iren.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())

    # Example 3D object
    sphere = vtk.vtkSphereSource()
    sphere.Update()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(sphere.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)


    ren3d.AddActor(actor)
    



    # fig = figure(fig_size=(800, 600), title="VTK Chart Actor", background_color="grey")

    chart_actor = add_chart_actor(
        renderer=ren2d,
        interactor=iren,
        position=(0.5, 0.05),
        size=(0.4, 0.2),
        title="Test Chart Actor",
        background_color="lightgrey",
        background_opacity=0.8,

    )
    x = np.linspace(0, 100, 200)
    y1 = np.sin(x / 10) * 50 + 50
    y2 = np.cos(x / 10) * 30 + 50
    y3 = np.sin(x / 5) * 20 + 40


    add_line_chart(x, y1, figure=chart_actor, color='blue', line_width=4, y_label='Summed Energies')
    add_line_chart(x, y2, figure=chart_actor, color='red', line_width=4, y_label='Scatterer Energies')
    add_line_chart(x, y3, figure=chart_actor, color='green', line_width=4, y_label='Absorber Energies')

    # set_x_axis_limits(chart_actor, x[0], x[-1])
    set_x_axis_title(chart_actor, 'Energy (keV)')
    set_y_axis_title(chart_actor, 'Counts')
    add_legend(chart_actor, inline=True)

    add_gridlines(chart_actor, color='black')

    
    ren2d.AddActor(chart_actor)

 
    # Enable draggable chart mode
    drag_style = DraggableChartInteractorStyle(chart_actor.GetScene().GetItem(0))
    drag_style.SetInteractor(iren)
    drag_style.SetScene(chart_actor.GetScene())

    # The camera keeps a plain style; the router hands pointer input over
    # the chart to the chart (ChartModeFilter).
    iren.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
    install_chart_mode(iren, chart_actor, drag_style)

    
    iren.Initialize()
    ren_win.Render()
    iren.Start()


if __name__ == "__main__":
    test_plots()
    # test_tree_heatmap_auto_collapse()
    # test_tanglegram_item()
    # test_block()
    # mpl_style_example()
    # test_in_vtk_render_window()
    # test_in_vtk_render_window_separate()
    # test_in_vtk_render_window_3()
    # test_draggable_charts()
    test_chart_actor()
