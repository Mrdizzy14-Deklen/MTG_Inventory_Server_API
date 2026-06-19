import Cookies from 'js-cookie';

const API_BASE_URL = 'https://vm.deklenn.dev';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || '';

export interface Card {
  card_name: string;
  type_line: string;
  quantity: number;
  [key: string]: any;
}

export async function registerUser(username: string, password: string, discord: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/register_user`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
    body: JSON.stringify({ username, password, discord }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || 'Registration failed');
  }

  return data;
}

export async function loginUser(username: string, password: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/login_user`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
    body: JSON.stringify({ username, password }),
  });

  if (!response.ok) {
    throw new Error('Invalid username or password');
  }

  const data = await response.json();
  return data.access_token;
}

async function fetchWithAuth(endpoint: string, options: RequestInit = {}) {
  const token = Cookies.get('authToken'); 
  
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
    ...options.headers,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (!response.ok) {
    let errorMessage = `API error: ${response.status} ${response.statusText}`;
    try {
      const errorData = await response.json();
      if (errorData.detail) errorMessage = errorData.detail;
    } catch (e) {}
    throw new Error(errorMessage);
  }

  return response.json();
}

export async function fetchInventory(): Promise<Card[]> {
  const data = await fetchWithAuth('/get_inventory');
  const rawInventory = data.inventory || data.cards || (Array.isArray(data) ? data : []);

  return rawInventory.map((item: any) => ({
    ...item
  }));
}

export async function fetchCards(filters: Record<string, any>): Promise<Card[]> {
  const data = await fetchWithAuth('/search_cards', {
    method: 'POST',
    body: JSON.stringify(filters),
  });

  const rawCards = data.cards || (Array.isArray(data) ? data : []);

  return rawCards.map((card: any) => ({
    ...card
  }));
}


export async function updatePreference(preference: {
  oracle_id: string;
  status: string;
  tag?: string;
  notes?: string;
}): Promise<any> {
  return fetchWithAuth('/set_preference', {
    method: 'POST',
    body: JSON.stringify(preference),
  });
}

export async function removePreference(preference: {
  oracle_id: string;
  status: string;
  tag?: string;
}): Promise<any> {
  return fetchWithAuth('/remove_preference', {
    method: 'POST',
    body: JSON.stringify(preference),
  });
}

export async function fetchPreferences(): Promise<any[]> {
  try {
    const data = await fetchWithAuth('/get_preferences', {
      method: 'GET',
    });
    
    return Array.isArray(data) ? data : (data.preferences || []);
  } catch (error) {
    console.error('Failed to fetch preferences:', error);
    return [];
  }
}

export interface BulkCardInput {
  name: string;
  quantity: number;
}

export interface BulkResponse {
  status: 'success' | 'error';
  message?: string;
  errors?: string[];
}

export async function addBulk(cards: BulkCardInput[]): Promise<BulkResponse> {
  console.log(JSON.stringify(cards));
  return fetchWithAuth('/add_bulk', {
    method: "POST",
    body: JSON.stringify({ cards }),
  });
}

export async function removeBulk(cards: BulkCardInput[]): Promise<BulkResponse> {
  return fetchWithAuth('/remove_bulk', {
    method: "POST",
    body: JSON.stringify({ cards }),
  });
}