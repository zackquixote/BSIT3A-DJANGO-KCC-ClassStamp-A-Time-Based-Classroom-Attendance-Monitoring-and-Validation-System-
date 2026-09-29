-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Sep 28, 2026 at 04:39 PM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `bsitcrud`
--

-- --------------------------------------------------------

--
-- Table structure for table `auth_group`
--

CREATE TABLE `auth_group` (
  `id` int(11) NOT NULL,
  `name` varchar(150) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `auth_group_permissions`
--

CREATE TABLE `auth_group_permissions` (
  `id` bigint(20) NOT NULL,
  `group_id` int(11) NOT NULL,
  `permission_id` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `auth_permission`
--

CREATE TABLE `auth_permission` (
  `id` int(11) NOT NULL,
  `name` varchar(255) NOT NULL,
  `content_type_id` int(11) NOT NULL,
  `codename` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `auth_permission`
--

INSERT INTO `auth_permission` (`id`, `name`, `content_type_id`, `codename`) VALUES
(1, 'Can add log entry', 1, 'add_logentry'),
(2, 'Can change log entry', 1, 'change_logentry'),
(3, 'Can delete log entry', 1, 'delete_logentry'),
(4, 'Can view log entry', 1, 'view_logentry'),
(5, 'Can add permission', 3, 'add_permission'),
(6, 'Can change permission', 3, 'change_permission'),
(7, 'Can delete permission', 3, 'delete_permission'),
(8, 'Can view permission', 3, 'view_permission'),
(9, 'Can add group', 2, 'add_group'),
(10, 'Can change group', 2, 'change_group'),
(11, 'Can delete group', 2, 'delete_group'),
(12, 'Can view group', 2, 'view_group'),
(13, 'Can add user', 4, 'add_user'),
(14, 'Can change user', 4, 'change_user'),
(15, 'Can delete user', 4, 'delete_user'),
(16, 'Can view user', 4, 'view_user'),
(17, 'Can add content type', 5, 'add_contenttype'),
(18, 'Can change content type', 5, 'change_contenttype'),
(19, 'Can delete content type', 5, 'delete_contenttype'),
(20, 'Can view content type', 5, 'view_contenttype'),
(21, 'Can add session', 6, 'add_session'),
(22, 'Can change session', 6, 'change_session'),
(23, 'Can delete session', 6, 'delete_session'),
(24, 'Can view session', 6, 'view_session'),
(25, 'Can add post', 7, 'add_post'),
(26, 'Can change post', 7, 'change_post'),
(27, 'Can delete post', 7, 'delete_post'),
(28, 'Can view post', 7, 'view_post'),
(29, 'Can add like', 8, 'add_like'),
(30, 'Can change like', 8, 'change_like'),
(31, 'Can delete like', 8, 'delete_like'),
(32, 'Can view like', 8, 'view_like'),
(33, 'Can add comment', 9, 'add_comment'),
(34, 'Can change comment', 9, 'change_comment'),
(35, 'Can delete comment', 9, 'delete_comment'),
(36, 'Can view comment', 9, 'view_comment'),
(37, 'Can add comment', 10, 'add_comment'),
(38, 'Can change comment', 10, 'change_comment'),
(39, 'Can delete comment', 10, 'delete_comment'),
(40, 'Can view comment', 10, 'view_comment'),
(41, 'Can add take profit level', 11, 'add_takeprofitlevel'),
(42, 'Can change take profit level', 11, 'change_takeprofitlevel'),
(43, 'Can delete take profit level', 11, 'delete_takeprofitlevel'),
(44, 'Can view take profit level', 11, 'view_takeprofitlevel'),
(45, 'Can add trade idea', 12, 'add_tradeidea'),
(46, 'Can change trade idea', 12, 'change_tradeidea'),
(47, 'Can delete trade idea', 12, 'delete_tradeidea'),
(48, 'Can view trade idea', 12, 'view_tradeidea'),
(49, 'Can add journal entry', 13, 'add_journalentry'),
(50, 'Can change journal entry', 13, 'change_journalentry'),
(51, 'Can delete journal entry', 13, 'delete_journalentry'),
(52, 'Can view journal entry', 13, 'view_journalentry'),
(53, 'Can add tblcourse', 14, 'add_tblcourse'),
(54, 'Can change tblcourse', 14, 'change_tblcourse'),
(55, 'Can delete tblcourse', 14, 'delete_tblcourse'),
(56, 'Can view tblcourse', 14, 'view_tblcourse'),
(57, 'Can add tblstudents', 15, 'add_tblstudents'),
(58, 'Can change tblstudents', 15, 'change_tblstudents'),
(59, 'Can delete tblstudents', 15, 'delete_tblstudents'),
(60, 'Can view tblstudents', 15, 'view_tblstudents'),
(61, 'Can add tblattendance', 16, 'add_tblattendance'),
(62, 'Can change tblattendance', 16, 'change_tblattendance'),
(63, 'Can delete tblattendance', 16, 'delete_tblattendance'),
(64, 'Can view tblattendance', 16, 'view_tblattendance'),
(65, 'Can add quiz question', 18, 'add_quizquestion'),
(66, 'Can change quiz question', 18, 'change_quizquestion'),
(67, 'Can delete quiz question', 18, 'delete_quizquestion'),
(68, 'Can view quiz question', 18, 'view_quizquestion'),
(69, 'Can add quiz', 17, 'add_quiz'),
(70, 'Can change quiz', 17, 'change_quiz'),
(71, 'Can delete quiz', 17, 'delete_quiz'),
(72, 'Can view quiz', 17, 'view_quiz'),
(73, 'Can add course schedule', 19, 'add_courseschedule'),
(74, 'Can change course schedule', 19, 'change_courseschedule'),
(75, 'Can delete course schedule', 19, 'delete_courseschedule'),
(76, 'Can view course schedule', 19, 'view_courseschedule'),
(77, 'Can add info', 20, 'add_info'),
(78, 'Can change info', 20, 'change_info'),
(79, 'Can delete info', 20, 'delete_info'),
(80, 'Can view info', 20, 'view_info');

-- --------------------------------------------------------

--
-- Table structure for table `auth_user`
--

CREATE TABLE `auth_user` (
  `id` int(11) NOT NULL,
  `password` varchar(128) NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) NOT NULL,
  `first_name` varchar(150) NOT NULL,
  `last_name` varchar(150) NOT NULL,
  `email` varchar(254) NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `auth_user`
--

INSERT INTO `auth_user` (`id`, `password`, `last_login`, `is_superuser`, `username`, `first_name`, `last_name`, `email`, `is_staff`, `is_active`, `date_joined`) VALUES
(1, 'pbkdf2_sha256$720000$EcUWmJliC0ddFa1gTCmeBh$ZU8a1pV8OcMxx3+eTljRu20P0fOSNv1BumXEwFAS968=', '2026-09-28 14:38:39.705136', 1, 'glenn', 'Glenn', 'Azuelo', 'glennazuelo1@gmail.com', 1, 1, '2026-05-12 14:09:37.605739'),
(2, 'pbkdf2_sha256$1200000$6tJ7297yjDHjAufSku1f6Q$/+XGBQy79azDzpUZ5QvzAQ7L3T608gS5zuB2/ATXeEc=', '2026-08-07 06:43:08.595063', 2, 'laravel', 'Laravel', 'Azuelo', 'glennazuelo12@gmail.com', 1, 1, '2026-06-25 10:30:12.000000');

-- --------------------------------------------------------

--
-- Table structure for table `auth_user_groups`
--

CREATE TABLE `auth_user_groups` (
  `id` bigint(20) NOT NULL,
  `user_id` int(11) NOT NULL,
  `group_id` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `auth_user_user_permissions`
--

CREATE TABLE `auth_user_user_permissions` (
  `id` bigint(20) NOT NULL,
  `user_id` int(11) NOT NULL,
  `permission_id` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `django_admin_log`
--

CREATE TABLE `django_admin_log` (
  `id` int(11) NOT NULL,
  `action_time` datetime(6) NOT NULL,
  `object_id` longtext DEFAULT NULL,
  `object_repr` varchar(200) NOT NULL,
  `action_flag` smallint(5) UNSIGNED NOT NULL CHECK (`action_flag` >= 0),
  `change_message` longtext NOT NULL,
  `content_type_id` int(11) DEFAULT NULL,
  `user_id` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Table structure for table `django_content_type`
--

CREATE TABLE `django_content_type` (
  `id` int(11) NOT NULL,
  `app_label` varchar(100) NOT NULL,
  `model` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `django_content_type`
--

INSERT INTO `django_content_type` (`id`, `app_label`, `model`) VALUES
(1, 'admin', 'logentry'),
(16, 'attendance', 'tblattendance'),
(2, 'auth', 'group'),
(3, 'auth', 'permission'),
(4, 'auth', 'user'),
(9, 'comments', 'comment'),
(5, 'contenttypes', 'contenttype'),
(19, 'courses', 'courseschedule'),
(17, 'courses', 'quiz'),
(18, 'courses', 'quizquestion'),
(14, 'courses', 'tblcourse'),
(20, 'info', 'info'),
(13, 'journal', 'journalentry'),
(8, 'likes', 'like'),
(7, 'posts', 'post'),
(10, 'replies', 'comment'),
(6, 'sessions', 'session'),
(15, 'students', 'tblstudents'),
(11, 'trade_ideas', 'takeprofitlevel'),
(12, 'trade_ideas', 'tradeidea');

-- --------------------------------------------------------

--
-- Table structure for table `django_migrations`
--

CREATE TABLE `django_migrations` (
  `id` bigint(20) NOT NULL,
  `app` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `applied` datetime(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `django_migrations`
--

INSERT INTO `django_migrations` (`id`, `app`, `name`, `applied`) VALUES
(1, 'contenttypes', '0001_initial', '2026-05-12 14:09:06.308582'),
(2, 'auth', '0001_initial', '2026-05-12 14:09:06.632369'),
(3, 'admin', '0001_initial', '2026-05-12 14:09:06.700429'),
(4, 'admin', '0002_logentry_remove_auto_add', '2026-05-12 14:09:06.704918'),
(5, 'admin', '0003_logentry_add_action_flag_choices', '2026-05-12 14:09:06.709665'),
(6, 'contenttypes', '0002_remove_content_type_name', '2026-05-12 14:09:06.762533'),
(7, 'auth', '0002_alter_permission_name_max_length', '2026-05-12 14:09:06.791377'),
(8, 'auth', '0003_alter_user_email_max_length', '2026-05-12 14:09:06.813827'),
(9, 'auth', '0004_alter_user_username_opts', '2026-05-12 14:09:06.818510'),
(10, 'auth', '0005_alter_user_last_login_null', '2026-05-12 14:09:06.850261'),
(11, 'auth', '0006_require_contenttypes_0002', '2026-05-12 14:09:06.851887'),
(12, 'auth', '0007_alter_validators_add_error_messages', '2026-05-12 14:09:06.856177'),
(13, 'auth', '0008_alter_user_username_max_length', '2026-05-12 14:09:06.877473'),
(14, 'auth', '0009_alter_user_last_name_max_length', '2026-05-12 14:09:06.899642'),
(15, 'auth', '0010_alter_group_name_max_length', '2026-05-12 14:09:06.921425'),
(16, 'auth', '0011_update_proxy_permissions', '2026-05-12 14:09:06.926218'),
(17, 'auth', '0012_alter_user_first_name_max_length', '2026-05-12 14:09:06.947849'),
(18, 'sessions', '0001_initial', '2026-05-12 14:09:06.981318'),
(19, 'posts', '0001_initial', '2026-06-01 07:13:46.447309'),
(20, 'posts', '0002_remove_post_image_url_remove_post_media_audio_and_more', '2026-06-01 07:25:48.895775'),
(21, 'posts', '0003_post_public_alter_post_audio_alter_post_image_and_more', '2026-06-03 08:31:42.808709'),
(22, 'likes', '0001_initial', '2026-06-04 08:08:47.316883'),
(23, 'comments', '0001_initial', '2026-06-05 03:40:04.764327'),
(24, 'replies', '0001_initial', '2026-06-06 04:17:08.248796'),
(25, 'comments', '0002_comment_likes', '2026-06-06 04:49:35.561559'),
(26, 'likes', '0002_alter_like_unique_together_alter_like_user_and_more', '2026-06-09 06:56:04.535594'),
(27, 'trade_ideas', '0001_initial', '2026-06-20 02:51:52.793523'),
(28, 'journal', '0001_initial', '2026-06-22 07:33:25.476093'),
(29, 'courses', '0001_initial', '2026-07-29 02:54:21.456579'),
(30, 'students', '0001_initial', '2026-07-29 02:54:21.471381'),
(31, 'courses', '0002_alter_tblcourse_courseid', '2026-07-29 03:09:15.864907'),
(32, 'attendance', '0001_initial', '2026-07-29 05:14:07.433798'),
(33, 'students', '0002_alter_tblstudents_idno', '2026-07-29 06:23:30.097050'),
(34, 'courses', '0003_tblcourse_status', '2026-08-02 13:53:39.847453'),
(35, 'courses', '0004_quiz_quizquestion', '2026-08-02 14:12:02.345417'),
(36, 'courses', '0005_quizquestion_question_type_and_more', '2026-08-02 14:18:13.022895'),
(37, 'courses', '0006_courseschedule', '2026-08-05 08:37:07.395337'),
(38, 'attendance', '0002_dedupe_and_unique', '2026-08-06 01:02:36.239230'),
(39, 'students', '0003_tblstudents_enrollment_type', '2026-08-07 05:52:07.447178'),
(40, 'courses', '0007_tblcourse_user', '2026-08-07 06:30:49.589447'),
(41, 'courses', '0008_assign_course_ownership', '2026-08-07 06:30:49.595082'),
(42, 'students', '0004_tblstudents_user', '2026-08-07 06:30:49.635627'),
(43, 'students', '0005_assign_student_ownership', '2026-08-07 06:30:49.642613'),
(44, 'courses', '0009_delete_courseschedule', '2026-09-28 13:26:33.001214'),
(45, 'info', '0001_initial', '2026-09-28 13:26:33.140759');

-- --------------------------------------------------------

--
-- Table structure for table `django_session`
--

CREATE TABLE `django_session` (
  `session_key` varchar(40) NOT NULL,
  `session_data` longtext NOT NULL,
  `expire_date` datetime(6) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `django_session`
--

INSERT INTO `django_session` (`session_key`, `session_data`, `expire_date`) VALUES
('0e34mgdvsji0i7w20ousc7ifdy390qei', '.eJxVjEsOgjAUAO_y1qbpK7QFlu49A3mf1qIGEgor490NCQvdzkzmDSPtWxn3mtZxUhgA4fLLmOSZ5kPog-b7YmSZt3VicyTmtNXcFk2v69n-DQrVAgNERueoiZ0Qaeu0s4Ex9I1YyphsVuEYMQf1PrP3JA3bjG0Qzdx3IcDnC_HkOIQ:1x9krb:jBqoDm7s3xLPqfpRgyApDbYdVnSkH-Xy4KfB1xfrY-w', '2026-10-08 14:55:55.689792'),
('0z3k2zjmmqiez3559lcz50nrom8fzfln', '.eJxVjEEOgyAQAP-yZ0NABZRj730DWVioVMRG8dT0742JF68zk_lCxJQDWaw1LJ-6g-EN5NXPtqYlgClHzg1YPOpkjz1sNhEYEHBjDv0cyinojeW1Mr-WuiXHzoRddmfPlUJ-XO1tMOE-gQHtRNtipwePSH1LA1dOqLHzHKMIPJJ3WouoSMropETfOR5FrzxFNw5Kwe8PwOZFsA:1xBCV5:GgCEqRrqXb5BCPQx4qhcntA7VVZB4kX_myb-iychwL4', '2026-10-12 14:38:39.707241'),
('1jyn03xuot89bx8qw2x9s3l0tayf7tnq', '.eJxVjMEOgyAQRP9lz4aIq0Q89t5vIAsLlYrYKJ6a_ns18eJpJvNm5guBYvJsqBQ_f8oGQ11BWtxkSpw9DHlPqQJDexnNvvnVRIYBJNwyS27y-QT8pvxahFtyWaMVZ0VcdBPPhX16XN3bwUjbeKwbtAqVllJhCJIshcNr1l3XukCK2xbJY4PqULSd7jWy7JhVr9CHmuD3B5yuRKA:1wU3on:vzg2cRp20vvN3l5rhCioqSKAbFuHU7GbPcfLYMmL-jE', '2026-06-15 14:40:41.437538'),
('2inqt59tihujff6t68g6z5boos5letut', '.eJxVjEsOgjAUAO_y1qbpK7QFlu49A3mf1qIGEgor490NCQvdzkzmDSPtWxn3mtZxUhgA4fLLmOSZ5kPog-b7YmSZt3VicyTmtNXcFk2v69n-DQrVAgNERueoiZ0Qaeu0s4Ex9I1YyphsVuEYMQf1PrP3JA3bjG0Qzdx3IcDnC_HkOIQ:1x9l9p:sCyUQ9REL4g10CUY6f8B4-JKHuW-iMWjVHLB7QhVOyc', '2026-10-08 15:14:45.635911'),
('2tyodn3kg943miaoex9sr60i4u3g6qqn', '.eJxVjEEOgyAQAP-yZ2NAUJBj730DWV2oVIRG8NT0742JF68zk_mCxxAdWazVbZ9awLAGYp5XW8PmwKQjxgYsHnWxR3G7DQQGONzYhPPq0inojemV2zmnuoepPZP2sqV9ZnLxcbW3wYJlAQOayNEomBa9kgoVZ3rUOA3eMdZz7FCiQqYkE-iF1F70AyeOWncjktcCfn-cq0Rt:1x0ILk:YQ0S0OyfXrJKzLZhKA7nEvN2Ge1JhhFol9rddC34jmM', '2026-09-12 12:39:56.413511'),
('3ajqa20ufv6f8n403d9i4of4wzvbl4vs', '.eJxVjEEOgyAQAP-yZ2NAUJBj730DWV2oVIRG8NT0742JF68zk_mCxxAdWazVbZ9awLAGYp5XW8PmwKQjxgYsHnWxR3G7DQQGONzYhPPq0inojemV2zmnuoepPZP2sqV9ZnLxcbW3wYJlAQOayNEomBa9kgoVZ3rUOA3eMdZz7FCiQqYkE-iF1F70AyeOWncjktcCfn-cq0Rt:1x3Mcy:9qd6vk-sM7TzFWPcMIjbrlVPMacRf58hQpa3IQHikj8', '2026-09-20 23:50:24.973404'),
('3c63molz1o8ewgkzshn8ygshg55chnoy', '.eJxVjM0OwiAQhN-FsyELXfnx6N1nILtApWogKe3J-O62SQ96m8z3zbxFoHUpYe15DlMSF6G0OP2WTPGZ607Sg-q9ydjqMk8sd0UetMtbS_l1Pdy_g0K9bGt2A0SljSaLOGRwNJLlpHVCNXo6W0BGyAbSllxkb0kRRERrEAbvxOcL8pI3LA:1wrAfm:iu2AZyH1-hx1Pu_UEqG46uLBj4FXt8wUZEK4FMHGABE', '2026-08-18 08:38:54.020840'),
('3ecoavsn1dzlphkus8udpektcybc6y58', '.eJxVjMEOgyAQRP9lz4aIq0Q89t5vIAsLlYrYKJ6a_ns18eJpJvNm5guBYvJsqBQ_f8oGQ11BWtxkSpw9DHlPqQJDexnNvvnVRIYBJNwyS27y-QT8pvxahFtyWaMVZ0VcdBPPhX16XN3bwUjbeKwbtAqVllJhCJIshcNr1l3XukCK2xbJY4PqULSd7jWy7JhVr9CHmuD3B5yuRKA:1wsEIf:ZntzF8HHtjCCIpirmuRoxbkYT163jv31HkP8QguRPRE', '2026-08-21 06:43:25.689121'),
('3ezhyuh3pu4l0nd3d0anzb7bor1c481t', '.eJxVjLEOwyAQQ_-FuUIlB6fQsXu_AR0clLQVSCGZqv57iZQhmWz52f4KR-uS3dri7CYWN6HE5Zh5Cu9YNsAvKs8qQy3LPHm5VeROm3xUjp_73j0dZGq5rwfwCGiVQkhJkafUvWVrjA6JkLUGijAAdgVv7GiBlWHGESGmK4nfH82sN3Q:1wrXA6:ohOT-d7azFCFSAtgQrebZE3seYhUf-sTRUZlUew7JzA', '2026-08-19 08:39:42.626147'),
('49znis6toihyod7gabh7oanu2src2pq9', '.eJxVjEsOgjAUAO_y1qbpK7QFlu49A3mf1qIGEgor490NCQvdzkzmDSPtWxn3mtZxUhgA4fLLmOSZ5kPog-b7YmSZt3VicyTmtNXcFk2v69n-DQrVAgNERueoiZ0Qaeu0s4Ex9I1YyphsVuEYMQf1PrP3JA3bjG0Qzdx3IcDnC_HkOIQ:1x9lNp:3sExgq1Hq5JaZCuFv5JVcmU6QC0W7jmNNfSwmDyLAak', '2026-10-08 15:29:13.014704'),
('59c5lpwgteknxa6lpw92rkt6ej4gvn47', '.eJxVjEsOgjAUAO_y1qbpK7QFlu49A3mf1qIGEgor490NCQvdzkzmDSPtWxn3mtZxUhgA4fLLmOSZ5kPog-b7YmSZt3VicyTmtNXcFk2v69n-DQrVAgNERueoiZ0Qaeu0s4Ex9I1YyphsVuEYMQf1PrP3JA3bjG0Qzdx3IcDnC_HkOIQ:1x9ksg:3K6iwSSep9NeOyI9rkrT3dt4VrHSxDssvLHKwiypVbU', '2026-10-08 14:57:02.540216'),
('64tcv7eur0i1kxnk4c7y4aurpumt1jrm', '.eJxVjMEOgyAQRP9lz4aIq0Q89t5vIAsLlYrYKJ6a_ns18eJpJvNm5guBYvJsqBQ_f8oGQ11BWtxkSpw9DHlPqQJDexnNvvnVRIYBJNwyS27y-QT8pvxahFtyWaMVZ0VcdBPPhX16XN3bwUjbeKwbtAqVllJhCJIshcNr1l3XukCK2xbJY4PqULSd7jWy7JhVr9CHmuD3B5yuRKA:1wyjRz:IG89D8nVNLf35DTGuRWJsfyNKLtoQG93jEzPGhS0qnU', '2026-09-08 05:11:55.644242'),
('7pju75ux3sfueck7orznemo8l7xw7wzg', '.eJxVjEEOgyAQAP-yZ2NAUJBj730DWV2oVIRG8NT0742JF68zk_mCxxAdWazVbZ9awLAGYp5XW8PmwKQjxgYsHnWxR3G7DQQGONzYhPPq0inojemV2zmnuoepPZP2sqV9ZnLxcbW3wYJlAQOayNEomBa9kgoVZ3rUOA3eMdZz7FCiQqYkE-iF1F70AyeOWncjktcCfn-cq0Rt:1x2NF2:Cc8IAGf4cMqEYgVVNzHdnfH0exxnCIisjj9I80c5p68', '2026-09-18 06:17:36.167042'),
('7vwk9cpiwm9xpxjyyf7jluc60c48kvyn', '.eJxVjEsOgjAUAO_y1qbpK7QFlu49A3mf1qIGEgor490NCQvdzkzmDSPtWxn3mtZxUhgA4fLLmOSZ5kPog-b7YmSZt3VicyTmtNXcFk2v69n-DQrVAgNERueoiZ0Qaeu0s4Ex9I1YyphsVuEYMQf1PrP3JA3bjG0Qzdx3IcDnC_HkOIQ:1x9kro:_lx6DhPYjuEcsZKw9bPY9L_JLHJmT2rO1Q3MIHMM56w', '2026-10-08 14:56:08.470270'),
('9c815ndy79ws6mdgl17vcajx77s2ol5n', '.eJxVjLEOwyAQQ_-FuUIlB6fQsXu_AR0clLQVSCGZqv57iZQhmWz52f4KR-uS3dri7CYWN6HE5Zh5Cu9YNsAvKs8qQy3LPHm5VeROm3xUjp_73j0dZGq5rwfwCGiVQkhJkafUvWVrjA6JkLUGijAAdgVv7GiBlWHGESGmK4nfH82sN3Q:1wrXA0:bz3bwGg3ShtBeY_QEdCyw2DxGscFes8JyxZo6L_Mx2Y', '2026-08-19 08:39:36.849567'),
('aqqunsfw5jamfohe0wos1cse46gj65g1', '.eJxVjMEOgyAQRP9lz4aIq0Q89t5vIAsLlYrYKJ6a_ns18eJpJvNm5guBYvJsqBQ_f8oGQ11BWtxkSpw9DHlPqQJDexnNvvnVRIYBJNwyS27y-QT8pvxahFtyWaMVZ0VcdBPPhX16XN3bwUjbeKwbtAqVllJhCJIshcNr1l3XukCK2xbJY4PqULSd7jWy7JhVr9CHmuD3B5yuRKA:1wNKbE:rmewH7zRQBnTMN0m9C1WxxNW5Nfn78saaCcCgYCYtl0', '2026-05-28 01:10:52.224532'),
('br2465dya6jwnawdhowrp5y0ldd760li', '.eJxVjEEOgyAQAP-yZ2NAUJBj730DWV2oVIRG8NT0742JF68zk_mCxxAdWazVbZ9awLAGYp5XW8PmwKQjxgYsHnWxR3G7DQQGONzYhPPq0inojemV2zmnuoepPZP2sqV9ZnLxcbW3wYJlAQOayNEomBa9kgoVZ3rUOA3eMdZz7FCiQqYkE-iF1F70AyeOWncjktcCfn-cq0Rt:1x3Tsj:_TGuM02D6OvgkZlmNKRUNziW8xqYY29NdxHbKLFmWQs', '2026-09-21 07:35:09.420204'),
('c2ffn6zj6nd6o2lhjl8e2tf1571huit0', '.eJxVjMEKwyAQRP_Fc5Ga1SX22Hu_QVZXa9qiEJNT6b83Qg7JaYZ5j_kKR-uS3dri7CYWNzGIy3HzFN6xdMAvKs8qQy3LPHnZFbnTJh-V4-e-u6eDTC33W_AIaJVCSEmRp7R1y9YYHRIhaw0UYQDcEryxowVWhhlHhJiuJH5_zkU3dQ:1wsEHG:feLazk0rYdBUUOKr_VG-LRNReJOSVfwfTF20uBDOSCs', '2026-08-21 06:41:58.343103'),
('feogqkx1x0vg05ikpgvfmz7dobp84rmc', '.eJxVjDsOwjAQBe_iGln-4iwlPWeIdr0LDiBbipMKcXeIlALaNzPvpUZclzKuXeZxYnVS1qnD70iYH1I3wnest6Zzq8s8kd4UvdOuL43led7dv4OCvXzrIToRC0jeWA4xCcQjeGc4Y5RrICcGJQMOTgJ4TEjBQiIfOUByYtX7AwbTOAU:1wrAfy:Tu1CjTvu1z9rIypaEruk587uAKpQi8d0ZMxyvsPG2Mc', '2026-08-18 08:39:06.386817'),
('hwj8z8k5fxa9na3zvtnusd9xfmiaotj2', '.eJxVjEEOgyAQAP-yZ2NAUJBj730DWV2oVIRG8NT0742JF68zk_mCxxAdWazVbZ9awLAGYp5XW8PmwKQjxgYsHnWxR3G7DQQGONzYhPPq0inojemV2zmnuoepPZP2sqV9ZnLxcbW3wYJlAQOayNEomBa9kgoVZ3rUOA3eMdZz7FCiQqYkE-iF1F70AyeOWncjktcCfn-cq0Rt:1x3nvC:79-CjwxDtuDNSW0VNq0E1OJczFn0AHw2iaU7z216TfI', '2026-09-22 04:59:02.180543'),
('i5vakvctxu73s5l7ef59jjf9tpqy6d1o', '.eJxVjLEOwyAQQ_-FuUIlB6fQsXu_AR0clLQVSCGZqv57iZQhmWz52f4KR-uS3dri7CYWN6HE5Zh5Cu9YNsAvKs8qQy3LPHm5VeROm3xUjp_73j0dZGq5rwfwCGiVQkhJkafUvWVrjA6JkLUGijAAdgVv7GiBlWHGESGmK4nfH82sN3Q:1wsEHG:wNdOecDfx_qQz9QXJF6mhp-YU7o-sJyd2kwXrm-HBTA', '2026-08-21 06:41:58.451850'),
('je31lxu8tuxmcoj16kmi8zcpwqv0tk5x', '.eJxVjMEOgyAQRP9lz8aIK0Q89t5vIAsLlYraCJ6a_ns18eJpJvNe5guBYvJsqBQ_f0qGoakgrW4yJc4ehmVPqQJDexnNnv1mIsMALdw2S27yywn4Tctrrd26lC3a-lTqi-b6ubJPj8u9HYyUx_MWrUKlhVAYgiBL4eiatZSdC6S465A8tqiORCt1r5GFZFa9Qh8agt8fnUdEoQ:1wVlX6:Aje4sw2JLOfc6plTFbos1gOAA8yUZsidF9y2f_WCNWQ', '2026-06-20 07:33:28.534590'),
('jmuceexhjkzq6onqzha24eq20efp12ij', '.eJxVjEEOgyAQAP-yZ2NAUJBj730DWV2oVIRG8NT0742JF68zk_mCxxAdWazVbZ9awLAGYp5XW8PmwKQjxgYsHnWxR3G7DQQGONzYhPPq0inojemV2zmnuoepPZP2sqV9ZnLxcbW3wYJlAQOayNEomBa9kgoVZ3rUOA3eMdZz7FCiQqYkE-iF1F70AyeOWncjktcCfn-cq0Rt:1x2pqk:MxSCCusvIKvkAW-TUjTKgwaVxcuXi_Rc9zMvE5hvAac', '2026-09-19 12:50:26.414216'),
('ltdey2r6fbc0nhd5t6ocap6smisii4fr', '.eJxVjMEOgyAQRP9lz8aIK0Q89t5vIAsLlYraCJ6a_ns18eJpJvNe5guBYvJsqBQ_f0qGoakgrW4yJc4ehmVPqQJDexnNnv1mIsMALdw2S27yywn4Tctrrd26lC3a-lTqi-b6ubJPj8u9HYyUx_MWrUKlhVAYgiBL4eiatZSdC6S465A8tqiORCt1r5GFZFa9Qh8agt8fnUdEoQ:1whOwC:rfWJrCYJFlKFd1_PKWva5nbz5vf8mpCJtEsL6MMRVTE', '2026-07-22 09:51:28.839793'),
('mbzknu4kpkawr3s0vvf634ospzzwsrvf', '.eJxVjEsOgjAUAO_y1qbpK7QFlu49A3mf1qIGEgor490NCQvdzkzmDSPtWxn3mtZxUhgA4fLLmOSZ5kPog-b7YmSZt3VicyTmtNXcFk2v69n-DQrVAgNERueoiZ0Qaeu0s4Ex9I1YyphsVuEYMQf1PrP3JA3bjG0Qzdx3IcDnC_HkOIQ:1x9lOB:I9WYm6abDUdwuXeMhNvtqjcodpbqvpCf5X4VE00gmXk', '2026-10-08 15:29:35.229487'),
('o0er7qcxpvsznfpyrbi7nkc43ktjt45y', '.eJxVjMEOgyAQRP9lz4aIq0Q89t5vIAsLlYrYKJ6a_ns18eJpJvNm5guBYvJsqBQ_f8oGQ11BWtxkSpw9DHlPqQJDexnNvvnVRIYBJNwyS27y-QT8pvxahFtyWaMVZ0VcdBPPhX16XN3bwUjbeKwbtAqVllJhCJIshcNr1l3XukCK2xbJY4PqULSd7jWy7JhVr9CHmuD3B5yuRKA:1wyHkC:WRpgfOnjPO25648LQ6TNsHZJ4Dm1ZXAkQnY5QlgMtlI', '2026-09-06 23:36:52.041422'),
('qfyw4hpgx2faw4m3q54byr2dco221lh3', '.eJxVjLEOwyAQQ_-FuUIlB6fQsXu_AR0clLQVSCGZqv57iZQhmWz52f4KR-uS3dri7CYWN6HE5Zh5Cu9YNsAvKs8qQy3LPHm5VeROm3xUjp_73j0dZGq5rwfwCGiVQkhJkafUvWVrjA6JkLUGijAAdgVv7GiBlWHGESGmK4nfH82sN3Q:1wrXAB:AegUMKakfH44vhSPP-OPpkxr-5Utbe-vfyhkdHlwGSc', '2026-08-19 08:39:47.444983'),
('rlgj6wxt7vwgwpdmxsoplcu7u859aaqy', '.eJxVjEsOgjAUAO_y1qbpK7QFlu49A3mf1qIGEgor490NCQvdzkzmDSPtWxn3mtZxUhgA4fLLmOSZ5kPog-b7YmSZt3VicyTmtNXcFk2v69n-DQrVAgNERueoiZ0Qaeu0s4Ex9I1YyphsVuEYMQf1PrP3JA3bjG0Qzdx3IcDnC_HkOIQ:1x9krg:TFLTq3JN8ItkaSf2vAYGtU5vSxvv9S3cYQ3WIjvI1Ww', '2026-10-08 14:56:00.798741'),
('sme92pftea9j1i5x0ooscaxsudls8pql', '.eJxVjEEOgyAQAP-yZ0NABZRj730DWVioVMRG8dT0742JF68zk_lCxJQDWaw1LJ-6g-EN5NXPtqYlgClHzg1YPOpkjz1sNhEYEHBjDv0cyinojeW1Mr-WuiXHzoRddmfPlUJ-XO1tMOE-gQHtRNtipwePSH1LA1dOqLHzHKMIPJJ3WouoSMropETfOR5FrzxFNw5Kwe8PwOZFsA:1x4Cnm:qW9dSnrBvvKkphbZJIARH57cqn7b3aQ6UgM5CGbiokM', '2026-09-23 07:33:02.239875'),
('swjje3v5mk3bbc0r4cr43oai4zyziuid', '.eJxVjEsOgjAUAO_y1qbpK7QFlu49A3mf1qIGEgor490NCQvdzkzmDSPtWxn3mtZxUhgA4fLLmOSZ5kPog-b7YmSZt3VicyTmtNXcFk2v69n-DQrVAgNERueoiZ0Qaeu0s4Ex9I1YyphsVuEYMQf1PrP3JA3bjG0Qzdx3IcDnC_HkOIQ:1x9krV:01Og5u64VzLqlYcDp21s5RRNDqfQZGXPaCbN3Nyf7jM', '2026-10-08 14:55:49.449985'),
('ttt8vv4blhjd3sigrt8nu0k6dp87imxc', '.eJxVjEsOgjAUAO_y1qbpK7QFlu49A3mf1qIGEgor490NCQvdzkzmDSPtWxn3mtZxUhgA4fLLmOSZ5kPog-b7YmSZt3VicyTmtNXcFk2v69n-DQrVAgNERueoiZ0Qaeu0s4Ex9I1YyphsVuEYMQf1PrP3JA3bjG0Qzdx3IcDnC_HkOIQ:1x9lOP:KuicCgkiYKc3-iWZ9IP4Oe9IhKnGSlrUaKod_tSYt48', '2026-10-08 15:29:49.345566'),
('z87ydqtr3q6d5eplfza2bzcl33nhfjdw', '.eJxVjMEKwyAQRP_Fc5Ga1SX22Hu_QVZXa9qiEJNT6b83Qg7JaYZ5j_kKR-uS3dri7CYWNzGIy3HzFN6xdMAvKs8qQy3LPHnZFbnTJh-V4-e-u6eDTC33W_AIaJVCSEmRp7R1y9YYHRIhaw0UYQDcEryxowVWhhlHhJiuJH5_zkU3dQ:1wsEHC:jgqzFKzskPhOyH8t9tDWOMpQPpL28E7zJvCfUA3YzNo', '2026-08-21 06:41:54.400657');

-- --------------------------------------------------------

--
-- Table structure for table `tblinfo`
--

CREATE TABLE `tblinfo` (
  `id` bigint(20) NOT NULL,
  `name` varchar(255) NOT NULL,
  `age` int(10) UNSIGNED NOT NULL CHECK (`age` >= 0),
  `address` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `user_id` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `tblinfo`
--

INSERT INTO `tblinfo` (`id`, `name`, `age`, `address`, `email`, `created_at`, `updated_at`, `user_id`) VALUES
(1, 'Glenn Azuelo1', 30, 'cauayan', 'glennazuelo1@gmail.com', '2026-09-28 14:16:01.072631', '2026-09-28 14:16:13.176731', 1);

--
-- Indexes for dumped tables
--

--
-- Indexes for table `auth_group`
--
ALTER TABLE `auth_group`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `name` (`name`);

--
-- Indexes for table `auth_group_permissions`
--
ALTER TABLE `auth_group_permissions`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  ADD KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`);

--
-- Indexes for table `auth_permission`
--
ALTER TABLE `auth_permission`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`);

--
-- Indexes for table `auth_user`
--
ALTER TABLE `auth_user`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `username` (`username`);

--
-- Indexes for table `auth_user_groups`
--
ALTER TABLE `auth_user_groups`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `auth_user_groups_user_id_group_id_94350c0c_uniq` (`user_id`,`group_id`),
  ADD KEY `auth_user_groups_group_id_97559544_fk_auth_group_id` (`group_id`);

--
-- Indexes for table `auth_user_user_permissions`
--
ALTER TABLE `auth_user_user_permissions`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `auth_user_user_permissions_user_id_permission_id_14a6b632_uniq` (`user_id`,`permission_id`),
  ADD KEY `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` (`permission_id`);

--
-- Indexes for table `django_admin_log`
--
ALTER TABLE `django_admin_log`
  ADD PRIMARY KEY (`id`),
  ADD KEY `django_admin_log_content_type_id_c4bce8eb_fk_django_co` (`content_type_id`),
  ADD KEY `django_admin_log_user_id_c564eba6_fk_auth_user_id` (`user_id`);

--
-- Indexes for table `django_content_type`
--
ALTER TABLE `django_content_type`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`);

--
-- Indexes for table `django_migrations`
--
ALTER TABLE `django_migrations`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `django_session`
--
ALTER TABLE `django_session`
  ADD PRIMARY KEY (`session_key`),
  ADD KEY `django_session_expire_date_a5c62663` (`expire_date`);

--
-- Indexes for table `tblinfo`
--
ALTER TABLE `tblinfo`
  ADD PRIMARY KEY (`id`),
  ADD KEY `tblinfo_user_id_4a36749d_fk_auth_user_id` (`user_id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `auth_group`
--
ALTER TABLE `auth_group`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `auth_group_permissions`
--
ALTER TABLE `auth_group_permissions`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `auth_permission`
--
ALTER TABLE `auth_permission`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=81;

--
-- AUTO_INCREMENT for table `auth_user`
--
ALTER TABLE `auth_user`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=14;

--
-- AUTO_INCREMENT for table `auth_user_groups`
--
ALTER TABLE `auth_user_groups`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `auth_user_user_permissions`
--
ALTER TABLE `auth_user_user_permissions`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `django_admin_log`
--
ALTER TABLE `django_admin_log`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `django_content_type`
--
ALTER TABLE `django_content_type`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=21;

--
-- AUTO_INCREMENT for table `django_migrations`
--
ALTER TABLE `django_migrations`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=46;

--
-- AUTO_INCREMENT for table `tblinfo`
--
ALTER TABLE `tblinfo`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `auth_group_permissions`
--
ALTER TABLE `auth_group_permissions`
  ADD CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  ADD CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`);

--
-- Constraints for table `auth_permission`
--
ALTER TABLE `auth_permission`
  ADD CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`);

--
-- Constraints for table `auth_user_groups`
--
ALTER TABLE `auth_user_groups`
  ADD CONSTRAINT `auth_user_groups_group_id_97559544_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
  ADD CONSTRAINT `auth_user_groups_user_id_6a12ed8b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`);

--
-- Constraints for table `auth_user_user_permissions`
--
ALTER TABLE `auth_user_user_permissions`
  ADD CONSTRAINT `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  ADD CONSTRAINT `auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`);

--
-- Constraints for table `django_admin_log`
--
ALTER TABLE `django_admin_log`
  ADD CONSTRAINT `django_admin_log_content_type_id_c4bce8eb_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`),
  ADD CONSTRAINT `django_admin_log_user_id_c564eba6_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`);

--
-- Constraints for table `tblinfo`
--
ALTER TABLE `tblinfo`
  ADD CONSTRAINT `tblinfo_user_id_4a36749d_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
