<?php
// ── ChatNCT Proxy: PHP → Python Flask ──
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }

$PYTHON = 'https://127.0.0.1:5000';
$path = $_SERVER['PATH_INFO'] ?? ($_GET['path'] ?? '');
if (!$path || $path === '/') { http_response_code(400); echo json_encode(['error'=>'No API path']); exit; }

$url = $PYTHON . $path;
$qs = preg_replace('/(&|^)path=[^&]*/', '', $_SERVER['QUERY_STRING'] ?? '');
if ($qs = ltrim($qs, '&')) $url .= '?' . $qs;

$ch = curl_init($url);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_FOLLOWLOCATION => true,
    CURLOPT_TIMEOUT => 120,
    CURLOPT_SSL_VERIFYPEER => false,
    CURLOPT_SSL_VERIFYHOST => false,
    CURLOPT_CUSTOMREQUEST => $_SERVER['REQUEST_METHOD'],
]);

if (in_array($_SERVER['REQUEST_METHOD'], ['POST','PUT','PATCH']))
    curl_setopt($ch, CURLOPT_POSTFIELDS, file_get_contents('php://input'));

$h = [];
if (isset($_SERVER['CONTENT_TYPE'])) $h[] = 'Content-Type: '.$_SERVER['CONTENT_TYPE'];
if (isset($_SERVER['HTTP_AUTHORIZATION'])) $h[] = 'Authorization: '.$_SERVER['HTTP_AUTHORIZATION'];
if ($h) curl_setopt($ch, CURLOPT_HTTPHEADER, $h);

$res = curl_exec($ch);
$code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$ct = curl_getinfo($ch, CURLINFO_CONTENT_TYPE);

if ($res === false) { http_response_code(502); echo json_encode(['error'=>'Python server unreachable']); exit; }

http_response_code($code);
header('Content-Type: '.($ct ?: 'application/json'));
echo $res;
