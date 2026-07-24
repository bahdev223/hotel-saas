$files = Get-ChildItem -Recurse -Include '*.html' -Path 'apps/pos/templates'
foreach ($f in $files) {
    $content = Get-Content $f.FullName -Raw
    if ($content -match 'alert\(') {
        $content = $content -replace 'alert\(', 'notifyError('
        Set-Content -Path $f.FullName -Value $content -NoNewline
        Write-Host "Updated $($f.Name)"
    }
}
