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
    // $conn is available from database.php
    global $conn;

    // Check students
    $stmt = $conn->prepare('SELECT id, name, student_code, password FROM students WHERE student_code = ?');
    $stmt->bind_param("s", $user);
    $stmt->execute();
    $result = $stmt->get_result();
    $row = $result->fetch_assoc();
    
    if ($row) {
        if ($row['password'] !== $pass) { echo json_encode(['status'=>'error','message'=>'Wrong password.']); exit; }
        echo json_encode(['status'=>'success','username'=>$row['name']?:$user,'role'=>'student','is_admin'=>false,'user_id'=>$row['student_code'],'access_token'=>bin2hex(random_bytes(16))]);
        exit;
    }

    // Check instructors
    $stmt = $conn->prepare('SELECT id, name, password FROM instructors WHERE name = ?');
    $stmt->bind_param("s", $user);
    $stmt->execute();
    $result = $stmt->get_result();
    $row = $result->fetch_assoc();
    
    if ($row) {
        if ($row['password'] !== $pass) { echo json_encode(['status'=>'error','message'=>'Wrong password.']); exit; }
        echo json_encode(['status'=>'success','username'=>$row['name'],'role'=>'instructor','is_admin'=>true,'user_id'=>(string)$row['id'],'access_token'=>bin2hex(random_bytes(16))]);
        exit;
    }

    echo json_encode(['status'=>'error','message'=>'User not found.']);
} catch (Exception $e) {
    echo json_encode(['status'=>'error','message'=>'DB error: '.$e->getMessage()]);
}
