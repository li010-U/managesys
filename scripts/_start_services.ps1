# Kill processes
taskkill /F /IM python.exe 2>$null
taskkill /F /IM node.exe 2>$null
Start-Sleep 3

# Start backend
$backendJob = Start-Job -ScriptBlock {
    Set-Location D:\managesys\backend
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8003
}

# Wait for backend
Start-Sleep 4

# Start frontend
$frontendJob = Start-Job -ScriptBlock {
    Set-Location D:\managesys\frontend
    npm run dev
}

Write-Host "Backend started on http://localhost:8003"
Write-Host "Frontend started on http://localhost:5173"
Write-Host "Ready!"
