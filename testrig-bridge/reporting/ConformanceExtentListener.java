package io.inji.conformance.reporting;

import com.aventstack.extentreports.ExtentReports;
import com.aventstack.extentreports.Status;
import com.aventstack.extentreports.reporter.ExtentHtmlReporter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.testng.ISuite;
import org.testng.ISuiteListener;
import org.testng.ITestListener;
import org.testng.ITestResult;

/** Report actual TestNG outcomes using the api-testrig's ExtentReports 3 API. */
public final class ConformanceExtentListener implements ITestListener, ISuiteListener {
    private final Map<ISuite, ExtentReports> reports = new ConcurrentHashMap<>();

    @Override public void onStart(ISuite suite) {
        try {
            Path directory = Path.of(System.getProperty("conformance.reportsDirectory", suite.getOutputDirectory()));
            Files.createDirectories(directory);
            ExtentReports report = new ExtentReports();
            report.attachReporter(new ExtentHtmlReporter(directory.resolve("conformance-extent.html").toString()));
            report.setSystemInfo("Suite", suite.getName());
            report.setSystemInfo("Evidence", "Actual TestNG module outcomes; REVIEW is not a conformance pass");
            reports.put(suite, report);
        } catch (Exception error) {
            throw new IllegalStateException("Cannot initialize conformance Extent report", error);
        }
    }

    private static String escaped(Object value) {
        return String.valueOf(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }

    private synchronized void record(ITestResult result, Status status) {
        ExtentReports report = reports.get(result.getTestContext().getSuite());
        if (report == null) throw new IllegalStateException("Extent report was not initialized");
        Object[] parameters = result.getParameters();
        String name = parameters.length > 0 ? String.valueOf(parameters[0]) : result.getMethod().getQualifiedName();
        var test = report.createTest(escaped(name));
        if (parameters.length > 1) test.info("Original suite status: " + escaped(parameters[1]));
        if (parameters.length > 2) test.info(escaped(parameters[2]));
        if (status == Status.PASS && parameters.length > 1 && "WARNING".equals(parameters[1])) status = Status.WARNING;
        test.log(status, result.getThrowable() == null ? "Observed TestNG outcome" : escaped(result.getThrowable().getMessage()));
    }

    @Override public void onTestSuccess(ITestResult result) { record(result, Status.PASS); }
    @Override public void onTestFailure(ITestResult result) { record(result, Status.FAIL); }
    @Override public void onTestSkipped(ITestResult result) { record(result, Status.SKIP); }
    @Override public void onFinish(ISuite suite) {
        ExtentReports report = reports.remove(suite);
        if (report != null) report.flush();
    }
}
