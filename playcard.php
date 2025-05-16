<?php
error_reporting(E_ALL);
ini_set('display_errors', 1);

// -------------------------------
// Configuration
// -------------------------------
define('SERVERROOT', "/var/www/html");

// Forbidden folder names or visible fragments (relative or substring match)
$FORBIDDEN_DIRS = [
    "music/Artist/Albumname",
    "Artist - ...album name ...",
    "wordpress",
    "phpgedview",
    // Add more entries as needed
];

// Directories to scan for media files
$MEDIA_DIRS = array_filter([
    SERVERROOT . "",
    "/home/radio/radio/ogg",
    getenv("AUDIO_PATH")
], fn($d) => $d && is_dir($d));

if (empty($MEDIA_DIRS)) {
    die("No valid media directories found.");
}

// Allowed media file extensions
$ALLOWED_EXTENSIONS = ['.mp3', '.mp4', '.ogg', '.ogv', '.webm'];

// Get relative path from absolute, based on MEDIA_DIRS
function get_relative_path($absolute_path) {
    global $MEDIA_DIRS;

    foreach ($MEDIA_DIRS as $base) {
        if (str_starts_with($absolute_path, $base)) {
            $rel = ltrim(substr($absolute_path, strlen($base)), DIRECTORY_SEPARATOR);
            return $rel;
        }
    }

    return $absolute_path; // fallback if not under any MEDIA_DIR
}

// Check if path is forbidden based on user-visible fragments
function is_forbidden($absolute_path) {
    global $FORBIDDEN_DIRS;

    $rel_path = get_relative_path($absolute_path);

    foreach ($FORBIDDEN_DIRS as $forbidden) {
        if (stripos($rel_path, $forbidden) !== false) {
            return true;
        }
    }

    return false;
}

// Filter MEDIA_DIRS to exclude forbidden entries
function filter_media_dirs($media_dirs, $forbidden_dirs) {
    $filtered = [];

    foreach ($media_dirs as $dir) {
        if (!is_forbidden($dir) && is_readable($dir)) {
            $filtered[] = $dir;
        }
    }

    return $filtered;
}

$MEDIA_DIRS = filter_media_dirs($MEDIA_DIRS, $FORBIDDEN_DIRS);

// -------------------------------
// CLI Mode
// -------------------------------
if (php_sapi_name() === 'cli') {
    $cli_args = $_SERVER['argv'];
    if (!isset($cli_args[1])) {
        fwrite(STDERR, "Usage: php playcard.php <title>\n");
        exit(1);
    }

    $title = $cli_args[1];
    $file_info = find_file($title, $ALLOWED_EXTENSIONS);

    if (!$file_info) {
        fwrite(STDERR, "Track not found: $title\n");
        exit(1);
    }

    echo "Playing: {$file_info['path']}\n";
    passthru("ffplay -autoexit -nodisp " . escapeshellarg($file_info['path']));
    exit(0);
}



// -------------------------------
// Utility Functions
// -------------------------------
function find_file($title_path, $extensions) {
    global $MEDIA_DIRS;

    foreach ($MEDIA_DIRS as $media_root) {
        $media_root_real = realpath($media_root);
        $full_path = realpath($media_root . '/' . $title_path);
        if ($full_path && is_file($full_path)) {
            if (strpos($full_path, $media_root_real . DIRECTORY_SEPARATOR) === 0) {
                $ext = strtolower('.' . pathinfo($full_path, PATHINFO_EXTENSION));
                if (in_array($ext, $extensions)) {
                    return [
                        'path' => $full_path,
                        'name' => basename($full_path),
                        'ext' => ltrim($ext, '.'),
                        'rel_path' => ltrim(str_replace($media_root_real, '', $full_path), '/\\')
                    ];
                }
            }
        }
    }

    // fallback: seach for filename in all directories
    foreach ($MEDIA_DIRS as $media_root) {
        $media_root_real = realpath($media_root);
        $iterator = new RecursiveIteratorIterator(
            new RecursiveDirectoryIterator($media_root_real, RecursiveDirectoryIterator::SKIP_DOTS)
        );
        foreach ($iterator as $file) {
            if ($file->isFile()) {
                $ext = strtolower('.' . $file->getExtension());
                if (in_array($ext, $extensions) &&
                    strpos($file->getFilename(), pathinfo($title_path, PATHINFO_FILENAME)) !== false) {
		    $real_file_path = realpath($file->getPathname());
		    if ($real_file_path && strpos($real_file_path, $media_root_real . DIRECTORY_SEPARATOR) === 0) {
   			 return [
        		'path' => $real_file_path,
        		'name' => $file->getFilename(),
        		'ext' => ltrim($ext, '.'),
        		'rel_path' => ltrim(str_replace($media_root_real, '', $real_file_path), '/\\')
    			];
		    }
	
                }
            }
        }
    }

    return null;
}


function find_cover_image($track_path, $track_name_base) {
    global $MEDIA_DIRS;

    $img_extensions = ['jpg', 'jpeg'];
    $track_dir = dirname($track_path);
    $candidate_images = [];

    foreach (scandir($track_dir) as $file) {
        $ext = strtolower(pathinfo($file, PATHINFO_EXTENSION));
        $name = pathinfo($file, PATHINFO_FILENAME);
        if (!in_array($ext, $img_extensions)) continue;

        $img_path = realpath($track_dir . '/' . $file);
        if (!$img_path || !is_file($img_path)) continue;

        $score = 0;

        // Normalize both names for comparison
        $normalized_track = strtolower(preg_replace('/[^a-z0-9]/i', '', $track_name_base));
        $normalized_name = strtolower(preg_replace('/[^a-z0-9]/i', '', $name));

        if ($normalized_name === $normalized_track) {
            $score = 100;
        } elseif (strpos($normalized_name, $normalized_track) !== false) {
            $score = 80;
        } elseif (preg_match('/\b(cover|folder|front|album)\b/i', $name) &&
                 stripos($name, $track_name_base) !== false) {
            // only if trackname exists
            $score = 70;
        }

        // Only include with meaningful relevance 
        if ($score > 0) {
            $candidate_images[] = ['path' => $img_path, 'score' => $score];
        }
    }

    if (count($candidate_images) === 1) {
        return $candidate_images[0]['path'];
    } elseif (count($candidate_images) > 1) {
        usort($candidate_images, fn($a, $b) => $b['score'] <=> $a['score']);
        return $candidate_images[0]['path'];
    }

    return null;
}


function send_file($filepath) {
    if (!file_exists($filepath)) {
        http_response_code(404);
        die("File not found.");
    }

    $mime_types = [
    '.mp3'  => 'audio/mpeg',
    '.mp4'  => 'video/mp4',
    '.ogg'  => 'audio/ogg',
    '.ogv'  => 'video/ogg', // or video/theora
    '.webm' => 'video/webm',
    '.jpg'  => 'image/jpeg',
    '.jpeg' => 'image/jpeg',
    ];


    $ext = strtolower(strrchr($filepath, '.'));
    $mime = $mime_types[$ext] ?? 'application/octet-stream';

    header('Content-Type: ' . $mime);
    header('Content-Length: ' . filesize($filepath));
    header('X-Content-Type-Options: nosniff');
    readfile($filepath);
    exit;
}

function generate_open_graph_tags($stream_url, $page_url, $file_name, $file_ext, $cover_url = null) {
    $file_name_escaped = htmlspecialchars($file_name, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    $file_ext_escaped = htmlspecialchars($file_ext, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    $og_image = $cover_url ?? 'https://jaquearnoux.de/radio.png';

    return <<<OG
    <meta property="og:type" content="music" />
    <meta property="og:title" content="Jaque Arnoux Radio $file_name_escaped" />
    <meta property="og:url" content="$page_url" />
    <meta property="og:image" content="$og_image" />
    <meta property="og:audio" content="$stream_url" />
    <meta property="og:audio:secure_url" content="$stream_url" />
    <meta property="og:audio:type" content="audio/$file_ext_escaped" />
    <meta property="og:video" content="$stream_url">
    <meta property="og:video:secure_url" content="$stream_url">
OG;
}



// [Rest of the file remains unchanged]


function generate_index() {
    global $MEDIA_DIRS, $ALLOWED_EXTENSIONS;

    $entries = [];

    foreach ($MEDIA_DIRS as $media_root) {
        $iterator = new RecursiveIteratorIterator(
            new RecursiveDirectoryIterator($media_root, RecursiveDirectoryIterator::SKIP_DOTS)
        );

        foreach ($iterator as $file) {
            if ($file->isFile()) {
		if (is_forbidden($file->getPathname())) continue;

		$ext = strtolower('.' . $file->getExtension());
                if (in_array($ext, $ALLOWED_EXTENSIONS)) {
                    $media_root_real = realpath($media_root);
                    $file_path_real = realpath($file->getPathname());
                    $rel_path = ltrim(str_replace($media_root_real, '', $file_path_real), '/\\');

                    $entries[] = [
                        'name' => $file->getFilename(),
                        'path' => str_replace('\\', '/', $rel_path)
                    ];
                }
            }
        }
    }

    usort($entries, 'compare_titles');
    return $entries;
}

function sort_key_locale($title) {
    $title = trim($title);
    if (empty($title)) return [3, ''];
    $first_char = $title[0];
    if (preg_match('/[A-Za-z]/', $first_char)) $priority = 0;
    elseif (preg_match('/\d/', $first_char)) $priority = 2;
    else $priority = 1;
    return [$priority, strtolower($title)];
}

function compare_titles($a, $b) {
    $ka = sort_key_locale($a['name']);
    $kb = sort_key_locale($b['name']);
    return $ka <=> $kb;
}

function generate_index_with_structure() {
    global $MEDIA_DIRS, $ALLOWED_EXTENSIONS;

    $folder_map = [];
    $all_files = [];

    foreach ($MEDIA_DIRS as $media_root) {
        $iterator = new RecursiveIteratorIterator(
            new RecursiveDirectoryIterator($media_root, RecursiveDirectoryIterator::SKIP_DOTS)
        );

        foreach ($iterator as $file) {
            if ($file->isFile()) {
		if (is_forbidden($file->getPathname())) continue;

		$ext = strtolower('.' . $file->getExtension());
                if (in_array($ext, $ALLOWED_EXTENSIONS)) {
                    $media_root_real = realpath($media_root);
                    $file_path_real = realpath($file->getPathname());
                    $rel_path = ltrim(str_replace($media_root_real, '', $file_path_real), '/\\');
                    $dir = dirname($rel_path);

                    $entry = [
                        'name' => $file->getFilename(),
                        'path' => str_replace('\\', '/', $rel_path),
                        'ext' => $ext
                    ];

                    $folder_map[$dir][] = $entry;
                    $all_files[] = $entry;
                }
            }
        }
    }

    // Sort entries in each folder
    foreach ($folder_map as &$files) {
        usort($files, fn($a, $b) => sort_key_locale($a['name']) <=> sort_key_locale($b['name']));
    }
    unset($files); // good practice

    // Sort folders
    uksort($folder_map, fn($a, $b) => sort_key_locale($a) <=> sort_key_locale($b));

    // Shuffle link
    $shuffle_track = $all_files ? $all_files[array_rand($all_files)] : null;
    $shuffle_url = $shuffle_track ? "?title=" . urlencode($shuffle_track['path']) : '#';

    return [$folder_map, $shuffle_url];
}




// -------------------------------
// Main Request Handler
// -------------------------------
if (isset($_GET['stream'])) {
    $stream_path = urldecode($_GET['stream']);
    $stream_path = str_replace('\\', '/', $stream_path);

    foreach ($MEDIA_DIRS as $media_root) {
        $full_path = realpath($media_root . '/' . $stream_path);
        if ($full_path && is_file($full_path)) {
            if (strpos($full_path, realpath($media_root)) === 0) {
                send_file($full_path);
            }
        }
    }

    http_response_code(404);
    die("Stream not found.");
}

// -------------------------------
// Index Page
// -------------------------------
$raw_title = $_GET['title'] ?? '';
$raw_title = trim(urldecode($raw_title));


$structured = true;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (isset($_POST['structured']) && $_POST['structured'] === "0") {
        $structured = false;
    }
} elseif (isset($_GET['structured']) && $_GET['structured'] === "0") {
    $structured = false;
}



if (empty($raw_title)) {
    if ($structured) {
        list($folder_map, $shuffle_url) = generate_index_with_structure();
    } else {
        $entries = generate_index();
    }

    header("Content-Type: text/html; charset=utf-8");
    echo "<!DOCTYPE html>
<html>
<head>
    <meta charset='utf-8'>
    <title>Playcard Music Streamer</title>
    <link rel='stylesheet' href='radio.css'>
</head>
<body>
    <h1>Playcard Music Streamer</h1>

    <form method='post' style='margin-bottom:1em'>
        <input type='hidden' name='structured' value='" . ($structured ? "0" : "1") . "'>
        <button type='submit'>" . ($structured ? "🔤 Flat" : "📁 Structured") . "</button>
    </form>";

    if ($structured) {
        echo "<p><a href='$shuffle_url'>🔀 Random  Title</a></p><div class='tracklist'>";
        foreach ($folder_map as $folder => $files) {
            echo "<div class='folder'><h2>" . htmlspecialchars($folder) . "</h2>";
            foreach ($files as $entry) {
                $link = htmlspecialchars("?title=" . urlencode($entry['path']));
                $name = htmlspecialchars($entry['name']);
                echo "<div class='track'><a href='$link'>$name</a></div>";
            }
            echo "</div>";
        }
    } else {
        echo "<div class='tracklist'>";
        foreach ($entries as $entry) {
            $link = htmlspecialchars("?title=" . urlencode($entry['path']));
            $name = htmlspecialchars($entry['name']);
            echo "<div class='track'><a href='$link'>$name</a></div>";
        }
    }

    echo "</div></body></html>";
    exit;
}



// -------------------------------
// Player Page
// -------------------------------
$file_info = find_file($raw_title, $ALLOWED_EXTENSIONS);

if (!$file_info) {
    http_response_code(404);
    die("Track not found.");
}

$scheme = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
$host = $_SERVER['HTTP_HOST'];
$base_url = "$scheme://$host";
$script_path = $_SERVER['SCRIPT_NAME'];
$stream_url = "$base_url$script_path?stream=" . urlencode($file_info['rel_path']);
$page_url = "$base_url$script_path?title=" . urlencode($raw_title);

// -------------------------------
// Check for cover image
// -------------------------------
$img_html = '';
// -------------------------------
// Intelligent check for cover image
// -------------------------------
$track_basename = pathinfo($file_info['name'], PATHINFO_FILENAME);
$found_img = find_cover_image($file_info['path'], $track_basename, $MEDIA_DIRS);

if ($found_img) {
    foreach ($MEDIA_DIRS as $media_root) {
        $media_root_real = realpath($media_root);
        if (strpos($found_img, $media_root_real) === 0) {
            $rel_img = ltrim(substr($found_img, strlen($media_root_real)), '/\\');
            $img_stream_url = "$base_url$script_path?stream=" . urlencode($rel_img);
            $img_html = "<img src='$img_stream_url' width='300' alt='Cover Image'><br>";
            break;
        }
    }
}

// -------------------------------
// Player Video or Audio
// ------------------------------

$player_html = '';
if (in_array($file_info['ext'], ['mp4', 'webm', 'ogv'])) {
    $player_html = <<<VIDEO
<video controls autoplay width="640">
    <source src="$stream_url" type="video/{$file_info['ext']}">
    Your browser does not support the video tag.
</video>
VIDEO;
} else {
    $player_html = <<<AUDIO
<audio controls autoplay>
    <source src="$stream_url" type="audio/{$file_info['ext']}">
    Your browser does not support the audio element.
</audio>
AUDIO;
}

$file_name_html = htmlspecialchars($file_info['name'], ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
$file_ext_html = htmlspecialchars($file_info['ext'], ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
$og_html = generate_open_graph_tags($stream_url, $page_url, $file_info['name'], $file_info['ext'], $img_stream_url ?? null);

    
    
// -------------------------------
// Output player HTML
// -------------------------------
header('Content-Type: text/html; charset=utf-8');
echo <<<HTML
<!DOCTYPE html>
<html prefix="og: http://ogp.me/ns#">
<head>
    <meta charset="utf-8">
    <title>$file_name_html</title>
    $og_html
    <meta property="og:title" content="Jaque Arnoux Radio $file_name_html" />
    <meta property="og:image" content="https://jaquearnoux.de/radio.png" />
    <link rel="stylesheet" href="radio.css" />
</head>
<body>
    <div class="player-container">
        <h1>$file_name_html</h1>
	$img_html
	$player_html
        <p><a href="$script_path">Back to index</a></p>
    </div>
    <script src="radio.js" async></script>
</body>
</html>
HTML;

