/** The only place ECharts is imported at runtime. Tree-shaken from echarts/core and loaded lazily by
 * Chart.tsx, so it never lands in the Hub's chunk (F18 budget; scripts/check-bundle.mjs checks this). */
import { BarChart, HeatmapChart, LineChart, ScatterChart } from "echarts/charts";
import { AxisPointerComponent, GridComponent, MarkLineComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([LineChart, BarChart, HeatmapChart, ScatterChart, GridComponent, TooltipComponent, AxisPointerComponent, MarkLineComponent, VisualMapComponent, CanvasRenderer]);

export default echarts;
