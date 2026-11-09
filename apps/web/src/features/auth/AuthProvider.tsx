import { createContext, useContext, useEffect, type ReactNode } from 'react';
import { api } from '../../lib/api';
import { useStore, type Dispatch } from '../../lib/mvi';
import { makeAuthEffects } from './api';
import { authReducer, initialAuthState, type AuthIntent, type AuthState } from './model';

const effects = makeAuthEffects(api);
const AuthContext = createContext<readonly [AuthState, Dispatch<AuthIntent>] | null>(null);
export function AuthProvider({ children }: { readonly children: ReactNode }) {
  const store = useStore(authReducer, initialAuthState, effects);
  const dispatch = store[1];
  useEffect(() => { dispatch({ type: 'start' }); }, [dispatch]);
  return <AuthContext.Provider value={store}>{children}</AuthContext.Provider>;
}
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('AuthProvider is required');
  return context;
}
