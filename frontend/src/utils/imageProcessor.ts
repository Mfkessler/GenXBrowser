/**
 * Image Processing Utilities for Species Photos
 * ==============================================
 * - Load and cache species photos
 * - Generate colored initials placeholders
 */

/**
 * Load an image and return its URL (no processing).
 * 
 * @param imageUrl - URL of the source image
 * @returns Promise resolving to the original image URL
 */
export async function loadImage(
  imageUrl: string
): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous'; // Enable CORS if needed
    
    img.onload = () => {
      // Simply return the original URL after confirming load
      resolve(imageUrl);
    };
    
    img.onerror = () => {
      reject(new Error(`Failed to load image: ${imageUrl}`));
    };
    
    img.src = imageUrl;
  });
}

/**
 * Generate a simple hash code from a string (for consistent color generation).
 * 
 * @param str - Input string
 * @returns Hash code
 */
function hashCode(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash);
}

/**
 * Generate a consistent color from a string.
 * Uses HSL to ensure good contrast and readability.
 * 
 * @param str - Input string (e.g., species name)
 * @returns HSL color string
 */
export function getColorForString(str: string): string {
  const hash = hashCode(str);
  
  // Use hash to generate hue (0-360)
  const hue = hash % 360;
  
  // Fixed saturation and lightness for good visibility
  const saturation = 65; // Not too saturated
  const lightness = 60;  // Medium lightness for good contrast
  
  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
}

/**
 * Extract initials from species name.
 * Examples:
 * - "Capnoides sempervirens" -> "CS"
 * - "capnoides_sempervirens" -> "CS"
 * - "Aquilegia coerulea" -> "AC"
 * 
 * @param speciesName - Species table name or display name
 * @returns Uppercase initials (max 2 characters)
 */
export function getSpeciesInitials(speciesName: string): string {
  // Split by spaces or underscores
  const parts = speciesName.split(/[\s_]+/).filter(p => p.length > 0);
  
  if (parts.length === 0) {
    return '??';
  }
  
  if (parts.length === 1) {
    // Single word - take first 2 characters
    return parts[0].substring(0, 2).toUpperCase();
  }
  
  // Multiple words - take first character of first 2 words
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

/**
 * Generate SVG data URL for a colored initials placeholder.
 * 
 * @param speciesName - Species name for generating initials and color
 * @param size - Size in pixels (default: 64)
 * @returns SVG data URL
 */
export function generateInitialsPlaceholder(
  speciesName: string,
  size: number = 64
): string {
  const initials = getSpeciesInitials(speciesName);
  const color = getColorForString(speciesName);
  
  // Calculate font size (approximately 40% of circle size)
  const fontSize = Math.floor(size * 0.4);
  
  const svg = `
    <svg width="${size}" height="${size}" xmlns="http://www.w3.org/2000/svg">
      <circle cx="${size/2}" cy="${size/2}" r="${size/2}" fill="${color}" />
      <text 
        x="50%" 
        y="50%" 
        dominant-baseline="central" 
        text-anchor="middle" 
        font-family="Arial, sans-serif" 
        font-size="${fontSize}" 
        font-weight="600" 
        fill="white"
      >${initials}</text>
    </svg>
  `.trim();
  
  // Encode SVG to data URL
  const encoded = encodeURIComponent(svg)
    .replace(/'/g, '%27')
    .replace(/"/g, '%22');
  
  return `data:image/svg+xml,${encoded}`;
}

/**
 * Photo cache for loaded images.
 * Avoids reloading the same image multiple times.
 */
const photoCache = new Map<string, string>();

/**
 * Get species photo URL (cached).
 * 
 * @param photoFilename - Photo filename from API
 * @param apiBaseUrl - Base URL for API requests
 * @returns Promise resolving to photo URL
 */
export async function getProcessedPhoto(
  photoFilename: string,
  apiBaseUrl: string
): Promise<string> {
  // Construct photo URL
  const photoUrl = `${apiBaseUrl}/api/species_photos/${photoFilename}`;
  
  // Check cache
  if (photoCache.has(photoUrl)) {
    return photoCache.get(photoUrl)!;
  }
  
  try {
    // Verify image loads
    await loadImage(photoUrl);
    
    // Cache URL
    photoCache.set(photoUrl, photoUrl);
    
    return photoUrl;
  } catch (error) {
    console.error(`Failed to load photo ${photoFilename}:`, error);
    throw error;
  }
}

/**
 * Clear the photo cache (useful for testing or memory management).
 */
export function clearPhotoCache(): void {
  photoCache.clear();
}
