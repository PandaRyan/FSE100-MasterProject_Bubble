// src/pages/BubbleBlitzMedium.tsx
// Medium mode page (Level 2): 90 seconds, 1-5 tap bubbles, 3 strikes = lose.

import React from "react";
import BubbleBlitzBoard from "../components/BubbleBlitzBoard";
import { LEVEL_MEDIUM } from "../api/bubbleApi";
import mediumBannerImg from "../assets/bubbleblitzm.png";

// ---- Constants (with sources from backend mediumbubble.py) ----
const MEDIUM_LEVEL_DURATION_SECONDS = 90; // Backend mediumbubble.py: LEVEL_DURATION = 90 s

const BubbleBlitzMedium: React.FC = () => {
  return (
    <BubbleBlitzBoard
      level={LEVEL_MEDIUM}
      modeTitle="MEDIUM MODE"
      modeBannerImg={mediumBannerImg}
      initialSeconds={MEDIUM_LEVEL_DURATION_SECONDS}
    />
  );
};

export default BubbleBlitzMedium;