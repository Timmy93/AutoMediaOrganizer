-- AutoMediaOrganizer Database Setup Script
-- This script creates the database and user for AutoMediaOrganizer
-- 
-- Usage:
--   mysql -u root -p < database_setup.sql
--
-- Or execute the commands manually in MySQL/MariaDB console

-- Create the database
CREATE DATABASE IF NOT EXISTS automediaorganizer 
    CHARACTER SET utf8mb4 
    COLLATE utf8mb4_unicode_ci;

-- Create the user (change password as needed)
CREATE USER IF NOT EXISTS 'automedia_user'@'localhost' IDENTIFIED BY 'change_this_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON automediaorganizer.* TO 'automedia_user'@'localhost';

-- Apply privileges
FLUSH PRIVILEGES;

-- Display confirmation
SELECT 'Database and user created successfully!' AS Status;
SELECT 'Database: automediaorganizer' AS Info;
SELECT 'User: automedia_user@localhost' AS Info;
SELECT 'Please change the default password in your config.toml' AS Warning;

-- Note: Tables will be created automatically by the application on first run
