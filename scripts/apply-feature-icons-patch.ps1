$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$indexPath = Join-Path $projectRoot "public\index.html"
$stylesPath = Join-Path $projectRoot "public\styles.css"
$testPath = Join-Path $projectRoot "tests\test_static_site.py"
$iconsPath = Join-Path $projectRoot "public\icons"

$iconFiles = @(
    "01_MaloneyIcons.png",
    "02_MaloneyIcons.png",
    "03_MaloneyIcons.png",
    "04_MaloneyIcons.png",
    "05_MaloneyIcons.png"
)

foreach ($iconFile in $iconFiles) {
    $fullPath = Join-Path $iconsPath $iconFile
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        throw "Icon-Datei fehlt: $fullPath"
    }
}

foreach ($requiredFile in @($indexPath, $stylesPath, $testPath)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Erforderliche Datei fehlt: $requiredFile"
    }
}

$index = Get-Content -LiteralPath $indexPath -Raw -Encoding UTF8

$replacements = @(
    '<img class="feature-icon feature-icon-image" src="icons/01_MaloneyIcons.png" alt="" aria-hidden="true">',
    '<img class="feature-icon feature-icon-image" src="icons/02_MaloneyIcons.png" alt="" aria-hidden="true">',
    '<img class="feature-icon feature-icon-image" src="icons/03_MaloneyIcons.png" alt="" aria-hidden="true">',
    '<img class="feature-icon feature-icon-image" src="icons/04_MaloneyIcons.png" alt="" aria-hidden="true">',
    '<img class="feature-icon feature-icon-image" src="icons/05_MaloneyIcons.png" alt="" aria-hidden="true">'
)

$pattern = '(?s)<svg class="feature-icon(?: github-icon)?"[^>]*>.*?</svg>'
$matches = [regex]::Matches($index, $pattern)

if ($matches.Count -ne 5) {
    throw "Erwartet wurden genau 5 Feature-SVGs, gefunden wurden $($matches.Count). Patch wurde nicht angewendet."
}

$builder = New-Object System.Text.StringBuilder
$lastIndex = 0

for ($i = 0; $i -lt $matches.Count; $i++) {
    $match = $matches[$i]
    [void]$builder.Append($index.Substring($lastIndex, $match.Index - $lastIndex))
    [void]$builder.Append($replacements[$i])
    $lastIndex = $match.Index + $match.Length
}

[void]$builder.Append($index.Substring($lastIndex))
$newIndex = $builder.ToString()

Set-Content -LiteralPath $indexPath -Value $newIndex -Encoding UTF8

$styles = Get-Content -LiteralPath $stylesPath -Raw -Encoding UTF8

$cssBlock = @'

.feature-icon-image {
  width: 72px;
  height: 72px;
  object-fit: contain;
  margin-bottom: 13px;
  filter: drop-shadow(0 5px 12px rgba(0, 0, 0, 0.58));
  transition: transform 180ms ease, filter 180ms ease;
}

.stat-card:hover .feature-icon-image,
.stat-card:focus-within .feature-icon-image {
  transform: translateY(-2px);
  filter:
    brightness(1.06)
    drop-shadow(0 7px 15px rgba(0, 0, 0, 0.64));
}

@media (max-width: 700px) {
  .feature-icon-image {
    width: 64px;
    height: 64px;
  }
}
'@

if ($styles -notmatch '\.feature-icon-image\s*\{') {
    $styles = $styles + $cssBlock
    Set-Content -LiteralPath $stylesPath -Value $styles -Encoding UTF8
}

$tests = Get-Content -LiteralPath $testPath -Raw -Encoding UTF8

$testBlock = @'


def test_feature_icon_pngs_exist_and_are_referenced() -> None:
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")

    icon_names = [
        "01_MaloneyIcons.png",
        "02_MaloneyIcons.png",
        "03_MaloneyIcons.png",
        "04_MaloneyIcons.png",
        "05_MaloneyIcons.png",
    ]

    for icon_name in icon_names:
        assert (PUBLIC / "icons" / icon_name).is_file()
        assert f'src="icons/{icon_name}"' in html

    assert html.count('class="feature-icon feature-icon-image"') == 5
'@

if ($tests -notmatch 'def test_feature_icon_pngs_exist_and_are_referenced') {
    $tests = $tests + $testBlock
    Set-Content -LiteralPath $testPath -Value $tests -Encoding UTF8
}

Write-Host ""
Write-Host "Feature-Icon-Patch erfolgreich angewendet." -ForegroundColor Green
Write-Host "Ersetzt: 5 SVG-Icons durch PNG-Dateien aus public\icons"
