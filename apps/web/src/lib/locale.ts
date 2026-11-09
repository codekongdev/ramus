/**
 * Screen language (roadmap 9.2). MVP ships Korean only; `en` arrives in Phase 4. Until the
 * account/browser resolution is built, the app runs on `DEFAULT_LOCALE`.
 */
export type Locale = 'ko' | 'en';

export const DEFAULT_LOCALE: Locale = 'ko';

export const SUPPORTED_LOCALES: readonly Locale[] = ['ko', 'en'];
