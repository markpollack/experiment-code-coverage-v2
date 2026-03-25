# JaCoCo Maven Plugin Patterns

## Standard Configuration

Add to `pom.xml` `<build><plugins>`:

```xml
<plugin>
    <groupId>org.jacoco</groupId>
    <artifactId>jacoco-maven-plugin</artifactId>
    <version>0.8.12</version>
    <executions>
        <execution>
            <goals>
                <goal>prepare-agent</goal>
            </goals>
        </execution>
        <execution>
            <id>report</id>
            <phase>test</phase>
            <goals>
                <goal>report</goal>
            </goals>
        </execution>
    </executions>
</plugin>
```

## Running Coverage

```bash
# Full cycle: clean, test, generate report
mvn clean test jacoco:report

# Just regenerate report (if tests already ran with agent attached)
mvn jacoco:report
```

## Report Locations

- HTML: `target/site/jacoco/index.html`
- XML: `target/site/jacoco/jacoco.xml` (machine-readable, used by JaCoCoReportParser)
- CSV: `target/site/jacoco/jacoco.csv`

## XML Report Structure

The XML report (`jacoco.xml`) contains counter elements:

```xml
<counter type="LINE" missed="15" covered="85"/>
<counter type="BRANCH" missed="8" covered="12"/>
<counter type="METHOD" missed="3" covered="17"/>
```

Coverage percentage = covered / (covered + missed) * 100

## Common Issues

### Agent Not Attaching
If coverage is always 0%, verify `prepare-agent` runs before `test` phase. The agent must be attached to the JVM running tests.

### Multi-Module Projects
In multi-module Maven projects, each module gets its own report. For aggregate coverage, use:
```xml
<execution>
    <id>report-aggregate</id>
    <phase>verify</phase>
    <goals>
        <goal>report-aggregate</goal>
    </goals>
</execution>
```

### Spring Boot Repackage Conflict
If `spring-boot-maven-plugin` repackages the JAR, JaCoCo's `prepare-agent` may not attach correctly. Ensure `jacoco:prepare-agent` runs in the `initialize` phase (before `test`).

## Excluding Code from Coverage

To exclude generated code or framework classes:

```xml
<configuration>
    <excludes>
        <exclude>**/Application.class</exclude>
        <exclude>**/config/**</exclude>
    </excludes>
</configuration>
```
