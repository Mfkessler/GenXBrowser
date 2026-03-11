import { expect, test, type Page } from '@playwright/test'

type HeatmapState = {
  tableName: string | null
  rowCount: number
  rowsLength: number
  processedRowsLength: number
  sortedRowsLength: number
  visibleColumnsLength: number
  hasSvg: boolean
  rects: number
}

const route = '/dev/genxbrowser/h/arabidopsis_thaliana,solanum_lycopersicum,oryza_sativa'

async function setGlobalFilter(page: Page, key: string, value: string) {
  await page.evaluate(
    ({ key, value }: { key: string; value: string }) => {
      const app = (document.querySelector('#app') as HTMLElement & { __vue_app__?: any })?.__vue_app__
      const provides = app?._context?.provides
      const piniaKey = provides
        ? Reflect.ownKeys(provides).find((entry) => String(entry) === 'Symbol(pinia)')
        : undefined

      if (!piniaKey) {
        throw new Error('Pinia instance not found on Vue app')
      }

      const pinia = provides[piniaKey]
      const filtersStore = pinia._s.get('filters')
      filtersStore.setFilters({
        [key]: {
          value,
          strict: false,
          empty: false,
        },
      })
    },
    { key, value },
  )
}

async function readHeatmapStates(page: Page): Promise<HeatmapState[]> {
  return page.evaluate(() => {
    function unwrap<T>(value: T | { value: T }): T {
      if (value && typeof value === 'object' && 'value' in value) {
        return value.value as T
      }
      return value as T
    }

    const panels = Array.from(document.querySelectorAll('main.flex.flex-col.h-full.overflow-hidden'))
    return panels.map((main) => {
      const instance = (main as HTMLElement & { __vueParentComponent?: any }).__vueParentComponent
      const setup = instance?.setupState || {}
      const container = main.querySelector('div.w-full.h-full')
      const svg = container?.querySelector('svg')
      return {
        tableName: unwrap<string | null>(setup.localTableName ?? null),
        rowCount: unwrap<number>(setup.rowCount ?? 0),
        rowsLength: unwrap<any[]>(setup.rows ?? []).length,
        processedRowsLength: unwrap<any[]>(setup.processedRows ?? []).length,
        sortedRowsLength: unwrap<any[]>(setup.sortedRows ?? []).length,
        visibleColumnsLength: unwrap<string[]>(setup.visibleColumns ?? []).length,
        hasSvg: Boolean(svg),
        rects: svg ? svg.querySelectorAll('rect').length : 0,
      }
    })
  })
}

test('renders all selected heatmaps after a shared TF family filter', async ({ page }) => {
  await page.goto(route)
  await page.waitForLoadState('networkidle')

  await setGlobalFilter(page, 'tf_family', 'MIKC')

  await expect
    .poll(async () => {
      const states = await readHeatmapStates(page)
      if (states.length !== 3) return false
      return states.every((state) =>
        state.rowCount > 0 &&
        state.rowsLength === state.rowCount &&
        state.processedRowsLength === state.rowCount &&
        state.sortedRowsLength === state.rowCount &&
        state.visibleColumnsLength > 0 &&
        state.hasSvg &&
        state.rects > 0,
      )
    }, {
      timeout: 20000,
      intervals: [250, 500, 1000],
    })
    .toBe(true)

  const states = await readHeatmapStates(page)
  expect(states).toHaveLength(3)
  for (const state of states) {
    expect(state.tableName).toBeTruthy()
    expect(state.rowCount).toBeGreaterThan(0)
    expect(state.rowsLength).toBe(state.rowCount)
    expect(state.processedRowsLength).toBe(state.rowCount)
    expect(state.sortedRowsLength).toBe(state.rowCount)
    expect(state.visibleColumnsLength).toBeGreaterThan(0)
    expect(state.hasSvg).toBe(true)
    expect(state.rects).toBeGreaterThan(0)
  }
})