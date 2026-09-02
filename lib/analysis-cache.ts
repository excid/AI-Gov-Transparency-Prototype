export type AnalysisStore = {
  get(key: string): Promise<unknown>;
  put(key: string, value: unknown): Promise<void>;
};

export async function analysisCacheKey(bytes: Uint8Array, version: string): Promise<string> {
  const copy = Uint8Array.from(bytes);
  const digest = await crypto.subtle.digest('SHA-256', copy);
  const hash = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
  return `${version}:${hash}`;
}

export async function getCachedAnalysis<T>(store: AnalysisStore, bytes: Uint8Array, version: string): Promise<T | undefined> {
  return await store.get(await analysisCacheKey(bytes, version)) as T | undefined;
}

export async function putCachedAnalysis<T>(store: AnalysisStore, bytes: Uint8Array, version: string, value: T): Promise<void> {
  await store.put(await analysisCacheKey(bytes, version), value);
}

export class IndexedDbAnalysisStore implements AnalysisStore {
  async database(): Promise<IDBDatabase> {
    return await new Promise((resolve, reject) => {
      const request = indexedDB.open('ai-gov-transparency', 1);
      request.onupgradeneeded = () => request.result.createObjectStore('analyses');
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async get(key: string): Promise<unknown> {
    const database = await this.database();
    return await new Promise((resolve, reject) => {
      const request = database.transaction('analyses', 'readonly').objectStore('analyses').get(key);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async put(key: string, value: unknown): Promise<void> {
    const database = await this.database();
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction('analyses', 'readwrite');
      transaction.objectStore('analyses').put(value, key);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
    });
  }
}
