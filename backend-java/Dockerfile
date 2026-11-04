FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /build
COPY settings.xml /root/.m2/settings.xml
COPY pom.xml .
RUN mvn -B -s /root/.m2/settings.xml dependency:go-offline
COPY src ./src
RUN mvn -B -s /root/.m2/settings.xml package -DskipTests

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /build/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
