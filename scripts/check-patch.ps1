$ErrorActionPreference = "Continue"

function Invoke-CheckStep {
    param(
        [Parameter(Mandatory)]
        [string]$Name,

        [Parameter(Mandatory)]
        [string[]]$Command
    )

    Write-Host ""
    Write-Host "=== $Name ==="

    $capturedOutput = @()

    & $Command[0] $Command[1..($Command.Count - 1)] 2>&1 |
        Tee-Object -Variable capturedOutput |
        ForEach-Object { Write-Host $_ }

    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        return
    }

    $clipboardText = @(
        "Fehler bei: $Name"
        "Befehl: $($Command -join ' ')"
        "Exitcode: $exitCode"
        ""
        ($capturedOutput | Out-String).TrimEnd()
    ) -join [Environment]::NewLine

    try {
        Set-Clipboard -Value $clipboardText
        Write-Host ""
        Write-Host "FEHLER: Nur die relevante Fehlermeldung wurde ins Clipboard kopiert."
        Write-Host "Bitte den Clipboard-Inhalt in ChatGPT einfügen."
    }
    catch {
        Write-Host ""
        Write-Host "FEHLER: Die Fehlermeldung konnte nicht ins Clipboard kopiert werden."
    }

    exit $exitCode
}

Invoke-CheckStep -Name "Alle Tests" -Command @(
    "uv", "run", "pytest"
)

Invoke-CheckStep -Name "Ruff automatisch korrigieren" -Command @(
    "uv", "run", "ruff", "check", ".", "--fix"
)

Invoke-CheckStep -Name "Ruff prüfen" -Command @(
    "uv", "run", "ruff", "check", "."
)

Write-Host ""
Write-Host "=== PATCH-PRÜFUNG ERFOLGREICH ==="
Write-Host "Alle Tests und Ruff-Prüfungen wurden bestanden."
