<?php

const REPOSITORY = 'fcarvajalbrown/riesgo-comunal';
const WORKFLOW = 'static-site.yml';
const BRANCH = 'main';

$tokenFile = getenv('HOME') . '/riesgo-comunal/github-token';
$token = is_readable($tokenFile) ? trim(file_get_contents($tokenFile)) : '';
if ($token === '') {
    fwrite(STDERR, "missing GitHub token in $tokenFile\n");
    exit(1);
}

$request = curl_init('https://api.github.com/repos/' . REPOSITORY . '/actions/workflows/' . WORKFLOW . '/dispatches');
curl_setopt_array($request, [
    CURLOPT_POST => true,
    CURLOPT_POSTFIELDS => json_encode(['ref' => BRANCH]),
    CURLOPT_HTTPHEADER => [
        'Accept: application/vnd.github+json',
        'Authorization: Bearer ' . $token,
        'X-GitHub-Api-Version: 2022-11-28',
        'User-Agent: riesgo-comunal-cron',
        'Content-Type: application/json',
    ],
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT => 30,
]);
$body = curl_exec($request);
$status = curl_getinfo($request, CURLINFO_RESPONSE_CODE);
$error = curl_error($request);
curl_close($request);

$stamp = gmdate('Y-m-d\TH:i:s\Z');
if ($status !== 204) {
    fwrite(STDERR, "$stamp dispatch failed: HTTP $status $error $body\n");
    exit(1);
}
echo "$stamp dispatched " . WORKFLOW . " on " . BRANCH . "\n";
