<?php
// ── ChatNCT Login API ──
// POST: { "username": "...", "password": "..." }

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { echo json_encode(['status'=>'error','message'=>'POST only']); exit; }

require_once __DIR__ . '/../../config/database.php';

$input = json_decode(file_get_contents('php://input'), true);
$user = trim($input['username'] ?? '');
$pass = $input['password'] ?? '';

if (!$user || !$pass) { echo json_encode(['status'=>'error','message'=>'Username and password required.']); exit; }

try {
    $db = getDB();

    // Check students
    $s = $db->prepare('SELECT id, name, student_code, password FROM students WHERE student_code = ?');
    $s->execute([$user]);
    $row = $s->fetch();
    if ($row) {
        if ($row['password'] !== $pass) { echo json_encode(['status'=>'error','message'=>'Wrong password.']); exit; }
        echo json_encode(['status'=>'success','username'=>$row['name']?:$user,'role'=>'student','is_admin'=>false,'user_id'=>$row['student_code'],'access_token'=>bin2hex(random_bytes(16))]);
        exit;
    }

    // Check instructors
    $s = $db->prepare('SELECT id, name, password FROM instructors WHERE name = ?');
    $s->execute([$user]);
    $row = $s->fetch();
    if ($row) {
        if ($row['password'] !== $pass) { echo json_encode(['status'=>'error','message'=>'Wrong password.']); exit; }
        echo json_encode(['status'=>'success','username'=>$row['name'],'role'=>'instructor','is_admin'=>true,'user_id'=>(string)$row['id'],'access_token'=>bin2hex(random_bytes(16))]);
        exit;
    }

    echo json_encode(['status'=>'error','message'=>'User not found.']);
} catch (PDOException $e) {
    echo json_encode(['status'=>'error','message'=>'DB error: '.$e->getMessage()]);
}
