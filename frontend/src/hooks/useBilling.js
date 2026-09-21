import { useState } from 'react';

/**
 * Hook to manage billing and auth related modals.
 */
export function useBilling() {
  const [showLogin, setShowLogin] = useState(false);
  const [showTopUp, setShowTopUp] = useState(false);
  const [showPlanChoice, setShowPlanChoice] = useState(false);
  const [showTrialUpgrade, setShowTrialUpgrade] = useState(false);
  const [topUpInfo, setTopUpInfo] = useState({ context: 'insufficient_funds' });

  return {
    showLogin, setShowLogin,
    showTopUp, setShowTopUp,
    showPlanChoice, setShowPlanChoice,
    showTrialUpgrade, setShowTrialUpgrade,
    topUpInfo, setTopUpInfo,
  };
}
