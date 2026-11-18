import React, { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import backgroundVideo from "../assets/backgroundvideo.mp4";
import back from "../assets/back.png";
import bubbleImg from "../assets/bubble.png"; // Import the bubble image
import "../fingercounting.css";

const FingerCounting: React.FC = () => {
    const navigate = useNavigate();
    
    const [videoSrc, setVideoSrc] = useState<string | null>(null);
    const [targetNumber, setTargetNumber] = useState<number>(3); 
    const [currentPrediction, setCurrentPrediction] = useState<number | null>(null);
    
    const [progress, setProgress] = useState<number>(0);
    const [hasWon, setHasWon] = useState<boolean>(false);
    
    const timerRef = useRef<NodeJS.Timeout | null>(null);
    const timeHeldRef = useRef<number>(0);
    const wsRef = useRef<WebSocket | null>(null);

    const startNewGame = () => {
        const newTarget = Math.floor(Math.random() * 5) + 1;
        setTargetNumber(newTarget);
        setHasWon(false);
        setProgress(0);
        timeHeldRef.current = 0;
    };

    useEffect(() => {
        startNewGame();

        const ws = new WebSocket("ws://localhost:8000/ws/video");
        wsRef.current = ws;

        ws.onopen = () => console.log("Connected to FastAPI WebSocket");

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            setVideoSrc(`data:image/jpeg;base64,${data.image}`);
            setCurrentPrediction(data.prediction);
        };

        ws.onerror = (error) => console.error("WebSocket Error:", error);

        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, []);

    useEffect(() => {
        if (hasWon) return; 

        if (currentPrediction === targetNumber) {
            if (!timerRef.current) {
                timerRef.current = setInterval(() => {
                    timeHeldRef.current += 100; 
                    setProgress((timeHeldRef.current / 1500) * 100); 

                    if (timeHeldRef.current >= 1500) {
                        setHasWon(true);
                        clearInterval(timerRef.current as NodeJS.Timeout);
                        timerRef.current = null;
                    }
                }, 100);
            }
        } else {
            if (timerRef.current) {
                clearInterval(timerRef.current);
                timerRef.current = null;
            }
            timeHeldRef.current = 0;
            setProgress(0);
        }

        return () => {
            if (timerRef.current) clearInterval(timerRef.current);
        };
    }, [currentPrediction, targetNumber, hasWon]);

    return (
        <div className="home-screen">
            <button className="back-button" onClick={() => navigate('/')}>
                <img src={back} alt="Back" className="back-icon" />
            </button>

            <video
                className="background-video"
                src={backgroundVideo}
                autoPlay
                loop
                muted
                playsInline
            />

            <div className="game-container">
                <div className="game-header">
                    <h2>Hold up <span>{targetNumber}</span> fingers!</h2>
                    
                    {/* NEW: Bubbles Progress Container */}
                    <div className="bubbles-container">
                        {[1, 2, 3, 4, 5].map((bubbleIndex) => {
                            // Each bubble represents 20% of the total time
                            const isActive = progress > (bubbleIndex - 1) * 20;
                            return (
                                <img
                                    key={bubbleIndex}
                                    src={bubbleImg}
                                    alt="progress bubble"
                                    className={`progress-bubble ${isActive ? 'active' : 'inactive'}`}
                                />
                            );
                        })}
                    </div>
                </div>

                <div className="video-frame">
                    {videoSrc ? (
                        <img src={videoSrc} alt="Webcam feed" />
                    ) : (
                        <p>Loading Camera Model...</p>
                    )}
                </div>

                {hasWon && (
                    <div className="win-overlay">
                        <h1>You Win!</h1>
                        <button onClick={startNewGame}>Play Again</button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default FingerCounting;