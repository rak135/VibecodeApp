import React from "react";

interface HomeScreenProps {
  title: string;
}

export function HomeScreen({ title }: HomeScreenProps): JSX.Element {
  return (
    <div className="home-screen">
      <h1>{title}</h1>
    </div>
  );
}

export default HomeScreen;
