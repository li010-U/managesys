// On-demand echarts: import only the chart types / components actually used,
// instead of the full echarts bundle (~1.1MB). This shrinks the shared echarts
// chunk and speeds up first paint (addressing the "giant echarts chunk / slow
// first screen" finding from the audit). If a new view needs a chart type or
// component not registered here, add it to the echarts.use(...) list below.
import * as echarts from 'echarts/core'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
} from 'echarts/components'
import { LabelLayout, UniversalTransition } from 'echarts/features'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  LineChart,
  BarChart,
  PieChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  LabelLayout,
  UniversalTransition,
  CanvasRenderer,
])

export default echarts
