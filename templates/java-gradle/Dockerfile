FROM eclipse-temurin:17-jdk-jammy

# Install Git and other essentials
RUN apt-get update && apt-get install -y \
    git \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Gradle 8.5
RUN curl -fsSL https://services.gradle.org/distributions/gradle-8.5-bin.zip -o /tmp/gradle.zip \
    && unzip /tmp/gradle.zip -d /opt \
    && ln -s /opt/gradle-8.5/bin/gradle /usr/local/bin/gradle \
    && rm /tmp/gradle.zip

# Set working directory
WORKDIR /workspace

# Set Git config for merge operations
RUN git config --global user.email "fixagent@verifier.local" \
    && git config --global user.name "FixAgent Verifier"

# Default command (keep container running)
CMD ["sleep", "infinity"]
