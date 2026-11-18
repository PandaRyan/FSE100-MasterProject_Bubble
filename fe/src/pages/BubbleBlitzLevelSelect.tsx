import { useNavigate } from "react-router-dom";
import { Link } from "react-router-dom";
import "../bubbleblitzlevelselect.css";
import backgroundVideo from "../assets/backgroundvideo.mp4";
import bubbleblitzeasy from "../assets/bubbleblitzeasy.png";
import bubbleblitzmedium from "../assets/bubbleblitzmedium.png";
import bubbleblitzhard from "../assets/bubbleblitzhard.png";
import back from "../assets/back.png";


function BubbleBlitzLevelSelect() {
  const navigate = useNavigate();

  return (
    <div className="home-screen">
      <video
        className="background-video"
        src={backgroundVideo}
        autoPlay
        loop
        muted
        playsInline
      />

      <button className="back-button" onClick={() => navigate('/')}>
        <img src={back} alt="Back" className="back-icon" />
      </button>

      <div className="button-container">
        <Link to="/bubbleblitzeasy">
          <img src={bubbleblitzeasy} alt="Bubble Blitz Easy" className="game-btn digi-btn" />
        </Link>

        <Link to="/bubbleblitzmedium">
          <img src={bubbleblitzmedium} alt="Bubble Blitz Medium" className="game-btn digi-btn" />
        </Link>

        <Link to="/bubbleblitzhard">
          <img src={bubbleblitzhard} alt="Bubble Blitz Hard" className="game-btn digi-btn" />
        </Link>
      </div>
    </div>
  );
}

export default BubbleBlitzLevelSelect;