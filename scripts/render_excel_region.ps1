param([string]$Source, [string]$Sheet, [string]$Range, [string]$Output)
$ErrorActionPreference = 'Stop'
$excel = $null
$book = $null
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.AskToUpdateLinks = $false
    $excel.AutomationSecurity = 3
    $book = $excel.Workbooks.Open($Source, 0, $true)
    $sheetObject = $book.Worksheets.Item($Sheet)
    $area = $sheetObject.Range($Range)
    $top = $area.Row; $left = $area.Column
    $bottom = $top + $area.Rows.Count - 1; $right = $left + $area.Columns.Count - 1
    foreach ($cell in $area.Cells) {
        if ($cell.MergeCells) {
            $merged = $cell.MergeArea
            $top = [Math]::Min($top, $merged.Row)
            $left = [Math]::Min($left, $merged.Column)
            $bottom = [Math]::Max($bottom, $merged.Row + $merged.Rows.Count - 1)
            $right = [Math]::Max($right, $merged.Column + $merged.Columns.Count - 1)
        }
    }
    $sheetObject.PageSetup.PrintArea = $sheetObject.Range($sheetObject.Cells.Item($top,$left),$sheetObject.Cells.Item($bottom,$right)).Address()
    $sheetObject.PageSetup.Zoom = $false
    $sheetObject.PageSetup.FitToPagesWide = 1
    $sheetObject.PageSetup.FitToPagesTall = $false
    $sheetObject.ExportAsFixedFormat(0, $Output)
} finally {
    if ($book) { $book.Close($false) }
    if ($excel) { $excel.Quit(); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($excel) }
}
