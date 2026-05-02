-- ChatNCT Database Setup (XAMPP MySQL)
CREATE DATABASE IF NOT EXISTS `gradproject` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `gradproject`;

-- Students
CREATE TABLE IF NOT EXISTS `students` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_code` VARCHAR(50) NOT NULL UNIQUE,
    `name` VARCHAR(255) NOT NULL,
    `password` VARCHAR(255) NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Instructors
CREATE TABLE IF NOT EXISTS `instructors` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(255) NOT NULL UNIQUE,
    `password` VARCHAR(255) NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Courses
CREATE TABLE IF NOT EXISTS `courses` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `course_code` VARCHAR(50) NOT NULL UNIQUE,
    `name` VARCHAR(255) NOT NULL,
    `instructor_id` INT DEFAULT NULL,
    FOREIGN KEY (`instructor_id`) REFERENCES `instructors`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Enrollment
CREATE TABLE IF NOT EXISTS `student_courses` (
    `student_id` INT NOT NULL,
    `course_id` INT NOT NULL,
    PRIMARY KEY (`student_id`, `course_id`),
    FOREIGN KEY (`student_id`) REFERENCES `students`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`course_id`) REFERENCES `courses`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Attendance Sessions
CREATE TABLE IF NOT EXISTS `attendance_sessions` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `session_code` VARCHAR(20) NOT NULL UNIQUE,
    `course_id` INT NOT NULL,
    `instructor_id` INT NOT NULL,
    `is_active` TINYINT(1) DEFAULT 1,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`course_id`) REFERENCES `courses`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`instructor_id`) REFERENCES `instructors`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Attendance Records
CREATE TABLE IF NOT EXISTS `attendance_records` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `session_id` INT NOT NULL,
    `student_id` INT NOT NULL,
    `verified_at` TIMESTAMP NULL DEFAULT NULL,
    FOREIGN KEY (`session_id`) REFERENCES `attendance_sessions`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`student_id`) REFERENCES `students`(`id`) ON DELETE CASCADE,
    UNIQUE KEY (`session_id`, `student_id`)
) ENGINE=InnoDB;

-- Sample Data
INSERT INTO `instructors` (`name`, `password`) VALUES
    ('Dr. Ahmed', 'admin123'), ('Dr. Mohamed', 'admin123')
ON DUPLICATE KEY UPDATE `name`=VALUES(`name`);

INSERT INTO `students` (`student_code`, `name`, `password`) VALUES
    ('20210001', 'Ehab Hossam', '123456'),
    ('20210002', 'Ali Hassan', '123456'),
    ('20210003', 'Sara Ahmed', '123456')
ON DUPLICATE KEY UPDATE `name`=VALUES(`name`);

INSERT INTO `courses` (`course_code`, `name`, `instructor_id`) VALUES
    ('CS101', 'Introduction to Computer Science', 1),
    ('CS201', 'Data Structures', 1),
    ('CS301', 'Artificial Intelligence', 2)
ON DUPLICATE KEY UPDATE `name`=VALUES(`name`);
