import { createClient, SupabaseClient } from '@supabase/supabase-js';

const SUPABASE_URL = ((import.meta as any).env?.VITE_SUPABASE_URL as string) || '';
const SUPABASE_ANON_KEY = ((import.meta as any).env?.VITE_SUPABASE_ANON_KEY as string) || '';

const isConfigured = Boolean(
  SUPABASE_URL &&
  SUPABASE_ANON_KEY &&
  SUPABASE_ANON_KEY !== 'undefined' &&
  SUPABASE_ANON_KEY.length > 10
);

// Gracefully initialize Supabase client only when valid keys are provided
export const supabase: SupabaseClient | null = isConfigured
  ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
  : null;

export const BUCKET_NAME = 'images';

/**
 * Upload a file to Supabase Storage if configured;
 * otherwise converts cleanly to an inline Base64 data URI so image uploads
 * work out-of-the-box with zero configuration errors.
 */
export async function uploadImageToSupabase(file: File, folder = 'kleanmaxpro'): Promise<string> {
  if (supabase) {
    try {
      const ext = file.name.split('.').pop() || 'jpg';
      const fileName = `${folder}/${Date.now()}_${Math.random().toString(36).substring(2, 8)}.${ext}`;

      const { error } = await supabase.storage
        .from(BUCKET_NAME)
        .upload(fileName, file, {
          cacheControl: '3600',
          upsert: true,
          contentType: file.type,
        });

      if (!error) {
        const { data: publicData } = supabase.storage
          .from(BUCKET_NAME)
          .getPublicUrl(fileName);
        if (publicData?.publicUrl) {
          return publicData.publicUrl;
        }
      }
    } catch (e) {
      console.warn('Supabase bucket upload failed, using Data URI fallback:', e);
    }
  }

  // Resilient fallback: Convert file to Base64 Data URI
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error('Failed to read image file'));
    reader.readAsDataURL(file);
  });
}

