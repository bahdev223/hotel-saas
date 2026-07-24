$files = Get-ChildItem -Recurse -Filter '*.html' -Path 'apps','templates' | Where-Object { $_.Length -gt 20000 } | Sort-Object Length -Descending | Select-Object -First 20
foreach ($f in $files) {
    $kb = [math]::Round($f.Length/1024,1)
    Write-Host "$kb KB  $($f.FullName)"
}

Write-Host "`n--- Templates with inline <script> blocks ---"
$scriptFiles = Get-ChildItem -Recurse -Filter '*.html' -Path 'apps','templates' | Where-Object { (Get-Content $_.FullName -Raw) -match '<script[^>]*>(?!.*src=)' }
Write-Host "Total: $($scriptFiles.Count) templates with inline script"
foreach ($f in ($scriptFiles | Sort-Object Length -Descending | Select-Object -First 15)) {
    $kb = [math]::Round($f.Length/1024,1)
    Write-Host "$kb KB  $($f.Name)"
}

Write-Host "`n--- fetch() calls ---"
$fetchCount = 0
Get-ChildItem -Recurse -Filter '*.html' -Path 'apps','templates' | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $matches = [regex]::Matches($content, "fetch\(")
    $fetchCount += $matches.Count
}
Write-Host "Total fetch() calls in templates: $fetchCount"

Write-Host "`n--- __x references ---"
$xRefs = 0
Get-ChildItem -Recurse -Filter '*.html' -Path 'apps','templates' | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $matches = [regex]::Matches($content, "__x")
    $xRefs += $matches.Count
}
Write-Host "Total __x references in templates: $xRefs"

Write-Host "`n--- alert() calls ---"
$alertCount = 0
Get-ChildItem -Recurse -Include '*.html','*.js' -Path 'apps','templates','static' | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $matches = [regex]::Matches($content, "alert\(")
    $alertCount += $matches.Count
}
Write-Host "Total alert() calls: $alertCount"
