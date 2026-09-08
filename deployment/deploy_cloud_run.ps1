# deployment/deploy_cloud_run.ps1
# Deploy the API first, then build and deploy the standalone Next.js service.
param(
    [string]$ProjectId = "sublime-night-507622-t9",
    [string]$Region = "us-central1",
    [string]$AgentEngineResource = "projects/602486879299/locations/us-central1/reasoningEngines/5446458885734924288",
    [Parameter(Mandatory = $true)]
    [string]$FirebaseApiKey
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$apiServiceAccount = "cultural-reference-api@$ProjectId.iam.gserviceaccount.com"
$webServiceAccount = "cultural-reference-web@$ProjectId.iam.gserviceaccount.com"
$image = "$Region-docker.pkg.dev/$ProjectId/cloud-run-source-deploy/cultural-reference-web:latest"

# Deploy FastAPI with Secret Manager injection and bounded public-demo resources.
try {
    Push-Location $repositoryRoot
    gcloud run deploy cultural-reference-api --source . --project=$ProjectId --region=$Region --service-account=$apiServiceAccount --allow-unauthenticated --set-secrets=PARALLEL_API_KEY=parallel-api-key:2 --set-env-vars="APP_ENV=production,GOOGLE_CLOUD_PROJECT=$ProjectId,GOOGLE_CLOUD_LOCATION=global,GOOGLE_GENAI_USE_VERTEXAI=True,GOOGLE_GENAI_MODEL=gemini-2.5-flash,USE_AGENT_ENGINE=True,AGENT_ENGINE_LOCATION=$Region,AGENT_ENGINE_RESOURCE_NAME=$AgentEngineResource,FIRESTORE_ENABLED=True,FRONTEND_ORIGINS=http://localhost:3000,REQUEST_TIMEOUT_SECONDS=280,MAX_HTTP_REQUEST_BYTES=57671680" --timeout=300 --concurrency=8 --max-instances=3 --memory=1Gi --cpu=1 --quiet
    $apiUrl = gcloud run services describe cultural-reference-api --project=$ProjectId --region=$Region --format="value(status.url)"

    # Build the browser bundle with only the public API URL and deploy it without secrets.
    Push-Location "$repositoryRoot\frontend"
    $firebaseAuthDomain = "$ProjectId.firebaseapp.com"
    gcloud builds submit . --project=$ProjectId --config="$repositoryRoot\deployment\cloudbuild.frontend.yaml" --substitutions="_API_BASE_URL=$apiUrl,_IMAGE=$image,_FIREBASE_API_KEY=$FirebaseApiKey,_FIREBASE_AUTH_DOMAIN=$firebaseAuthDomain,_FIREBASE_PROJECT_ID=$ProjectId" --quiet
    gcloud run deploy cultural-reference-web --image=$image --project=$ProjectId --region=$Region --service-account=$webServiceAccount --allow-unauthenticated --concurrency=40 --max-instances=3 --memory=512Mi --cpu=1 --quiet
    $webUrl = gcloud run services describe cultural-reference-web --project=$ProjectId --region=$Region --format="value(status.url)"
    $projectNumber = gcloud projects describe $ProjectId --format="value(projectNumber)"
    $projectNumberWebUrl = "https://cultural-reference-web-$projectNumber.$Region.run.app"
    Pop-Location

    # Restrict production CORS to the deployed frontend while retaining local development.
    # Cloud Run exposes both the canonical hash URL and the project-number URL.
    gcloud run services update cultural-reference-api --project=$ProjectId --region=$Region "--update-env-vars=^@^FRONTEND_ORIGINS=http://localhost:3000,$webUrl,$projectNumberWebUrl" --quiet
    Write-Output "Backend: $apiUrl"
    Write-Output "Frontend: $webUrl"
}
catch {
    throw
}
finally {
    while ((Get-Location).Path -ne $repositoryRoot -and (Get-Location).Path.Length -gt 3) {
        Pop-Location
    }
}
