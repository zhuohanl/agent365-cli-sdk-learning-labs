#requires -Version 7.0
<#
.SYNOPSIS
Read one companion registration with the connector's Graph application identity.
.DESCRIPTION
Read A365_TENANT_ID and A365_CLIENT_ID from the Lab 20 root .env file. For the
connector identity probe, these must match GRAPH_TENANT_ID and GRAPH_CLIENT_ID
in the active Container App revision. Enter that application's client secret
when prompted. Use the exact registeredAgentId from the connector mapping.
The script makes no Graph writes and does not save credentials or responses.
.EXAMPLE
.\Get-CompanionRegistration.ps1 -RegistrationId '<registeredAgentId>'
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string] $RegistrationId,

    [ValidateNotNullOrEmpty()]
    [string] $EnvFile = (Join-Path $PSScriptRoot '..\..\.env'),

    [System.Security.SecureString] $ClientSecret,

    [ValidateRange(1, 120)]
    [int] $TimeoutSeconds = 30
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Read-ApplicationIds {
    param([string] $Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "The .env file was not found: $Path"
    }
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path -Encoding utf8) {
        if ($line -match '^\s*(A365_TENANT_ID|A365_CLIENT_ID)\s*=(.*)$') {
            $values[$Matches[1]] = $Matches[2].Trim()
        }
    }
    $ids = @{}
    foreach ($name in @('A365_TENANT_ID', 'A365_CLIENT_ID')) {
        $value = [string] $values[$name]
        if ($value -match '^([''"])(.*)\1$') {
            $value = $Matches[2]
        }
        else {
            $value = ($value -replace '\s+#.*$', '').Trim()
        }
        $id = [guid]::Empty
        if (-not [guid]::TryParse($value, [ref] $id) -or $id -eq [guid]::Empty) {
            throw "Set $name to a non-empty GUID in the .env file. The value was not printed."
        }
        $ids[$name] = $id
    }
    return $ids
}

function Read-JsonResponse {
    param([string] $Content, [string] $Operation)

    try {
        return ConvertFrom-Json -InputObject $Content -AsHashtable -ErrorAction Stop
    }
    catch {
        throw "$Operation returned an invalid JSON response. The response body was not printed."
    }
}

function Protect-ErrorText {
    param([string] $Text, [string[]] $SensitiveValues)

    foreach ($value in $SensitiveValues) {
        if (-not [string]::IsNullOrEmpty($value)) {
            $Text = $Text.Replace($value, '<REDACTED>')
        }
    }
    return $Text
}

if ([string]::IsNullOrWhiteSpace($RegistrationId)) {
    throw 'RegistrationId must not be blank.'
}
$applicationIds = Read-ApplicationIds -Path $EnvFile
$TenantId = $applicationIds['A365_TENANT_ID']
$ClientId = $applicationIds['A365_CLIENT_ID']
if ($null -eq $ClientSecret) {
    $ClientSecret = Read-Host 'Client secret for the connector Graph application (not the secret ID)' -AsSecureString
}
if ($ClientSecret.Length -eq 0) {
    throw 'The client secret must not be empty.'
}

$secretPointer = [IntPtr]::Zero
$plainSecret = $null
$accessToken = $null
$tokenBody = $null
$tokenResponse = $null
$tokenResult = $null
$headers = $null

try {
    $secretPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($ClientSecret)
    $plainSecret = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPointer)
    $tokenBody = @{
        client_id = $ClientId.ToString()
        client_secret = $plainSecret
        grant_type = 'client_credentials'
        scope = 'https://graph.microsoft.com/.default'
    }

    Write-Host 'Requesting a Microsoft Graph application token.'
    try {
        $tokenResponse = Invoke-WebRequest `
            -Uri "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token" `
            -Method Post `
            -ContentType 'application/x-www-form-urlencoded' `
            -Body $tokenBody `
            -TimeoutSec $TimeoutSeconds `
            -MaximumRedirection 0 `
            -SkipHttpErrorCheck
    }
    catch {
        throw 'The token request failed before an HTTP response was available. Check connectivity and the request timeout.'
    }

    $tokenStatus = [int] $tokenResponse.StatusCode
    $tokenResult = Read-JsonResponse -Content $tokenResponse.Content -Operation 'Token request'
    if ($tokenStatus -ne 200) {
        $code = Protect-ErrorText -Text ([string] $tokenResult['error']) -SensitiveValues @($plainSecret)
        $message = Protect-ErrorText -Text ([string] $tokenResult['error_description']) -SensitiveValues @($plainSecret)
        throw "Token request failed (HTTP $tokenStatus): $code. $message"
    }
    $accessToken = [string] $tokenResult['access_token']
    if ([string]::IsNullOrWhiteSpace($accessToken)) {
        throw 'The token response did not contain an access token.'
    }

    $encodedId = [Uri]::EscapeDataString($RegistrationId)
    $headers = @{
        Authorization = "Bearer $accessToken"
        Accept = 'application/json'
    }
    Write-Host 'Reading the registration with the connector Graph application identity.'
    try {
        $response = Invoke-WebRequest `
            -Uri "https://graph.microsoft.com/beta/copilot/agentRegistrations/$encodedId" `
            -Method Get `
            -Headers $headers `
            -TimeoutSec $TimeoutSeconds `
            -MaximumRedirection 0 `
            -SkipHttpErrorCheck
    }
    catch {
        throw 'The registration GET failed before an HTTP response was available. Check connectivity and the request timeout.'
    }

    $status = [int] $response.StatusCode
    Write-Host "Registration GET: HTTP $status"
    if ($status -ne 200) {
        if ([string]::IsNullOrWhiteSpace($response.Content)) {
            throw "Registration GET failed (HTTP $status); the response body was empty."
        }
        $failure = Read-JsonResponse -Content $response.Content -Operation "Registration GET (HTTP $status)"
        $graphError = $failure['error']
        if ($graphError -isnot [System.Collections.IDictionary]) {
            throw "Registration GET failed (HTTP $status); the response did not contain a Graph error object."
        }
        $code = Protect-ErrorText -Text ([string] $graphError['code']) -SensitiveValues @($plainSecret, $accessToken)
        $message = Protect-ErrorText -Text ([string] $graphError['message']) -SensitiveValues @($plainSecret, $accessToken)
        throw "Registration GET failed (HTTP $status): $code. $message"
    }

    $registration = Read-JsonResponse -Content $response.Content -Operation 'Registration GET'
    if ($registration['id'] -cne $RegistrationId) {
        throw 'Registration GET returned HTTP 200, but the returned id did not match the requested registration ID.'
    }
    [ordered] @{
        httpStatus = $status
        tenantId = $TenantId.ToString()
        clientId = $ClientId.ToString()
        registration = [ordered] @{
            id = $registration['id']
            sourceAgentId = $registration['sourceAgentId']
            displayName = $registration['displayName']
            originatingStore = $registration['originatingStore']
            createdBy = $registration['createdBy']
            managedByAppId = $registration['managedByAppId']
            agentIdentityId = $registration['agentIdentityId']
            agentIdentityBlueprintId = $registration['agentIdentityBlueprintId']
        }
    } | ConvertTo-Json -Depth 4
}
finally {
    if ($secretPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPointer)
    }
    if ($null -ne $tokenBody) { $tokenBody.Clear() }
    if ($null -ne $tokenResult) { $tokenResult.Clear() }
    if ($null -ne $headers) { $headers.Clear() }
    $plainSecret = $null
    $accessToken = $null
    $tokenResponse = $null
    $ClientSecret = $null
}
