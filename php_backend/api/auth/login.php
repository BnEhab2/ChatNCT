<?php
header('Content-Type: application/json'); // for content type to be send
header('Access-Control-Allow-Origin: *'); // allow any domain to access API
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {  //server test 204 response
    http_response_code(204);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') { //any server response will be post only
    echo json_encode(['status' => 'error', 'message' => 'POST only']); 
    exit;
}

require_once __DIR__ . '/../../config/database.php'; //database path

$input = json_decode(file_get_contents('php://input'), true); // Decode JSON request to an array
$user = trim($input['username'] ?? ''); // Get username and trim spaces
$pass = $input['password'] ?? ''; // Get password

if (!$user || !$pass) { // Check for username and password presence
    echo json_encode(['status' => 'error', 'message' => 'Username and password required']);
    exit;
}

$stmt = $conn->prepare('SELECT id, name, student_code, password FROM students WHERE student_code = ?'); // Prepare SQL statement to fetch student data using student_code
$stmt->bind_param("s", $user); // Bind the user to the SQL statement parameter as a string
$stmt->execute(); // Execute the SQL statement
$result = $stmt->get_result(); // Get the result of the execution
$row = $result->fetch_assoc(); // Fetch the first row of the result as an associative array

if ($row) {
    if ($row['password'] !== $pass) {
        echo json_encode(['status' => 'error', 'message' => 'Wrong password']);
        exit;
    }
    echo json_encode([
        'status'       => 'success',
        'username'     => $row['name'] ?: $user,
        'role'         => 'student',
        'is_admin'     => false,
        'user_id'      => $row['student_code'],
        'access_token' => bin2hex(random_bytes(16))
    ]);
    exit;
}

$stmt = $conn->prepare('SELECT id, name, password FROM instructors WHERE name = ?');
$stmt->bind_param("s", $user);
$stmt->execute();
$result = $stmt->get_result();
$row = $result->fetch_assoc();

if ($row) {
    if ($row['password'] !== $pass) {
        echo json_encode(['status' => 'error', 'message' => 'Wrong password']);
        exit;
    }
    echo json_encode([
        'status'       => 'success',
        'username'     => $row['name'],
        'role'         => 'instructor',
        'is_admin'     => true,
        'user_id'      => (string) $row['id'],
        'access_token' => bin2hex(random_bytes(16))
    ]);
    exit;
}
echo json_encode(['status' => 'error', 'message' => 'User not found']);
?>
