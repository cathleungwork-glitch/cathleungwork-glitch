import java.awt.Font;
import java.awt.Rectangle;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.FileReader;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import javax.imageio.ImageIO;
import javax.swing.JFrame;
import javax.swing.JRadioButton;
import javax.swing.JScrollPane;
import javax.swing.JTextArea;
import javax.swing.JTextField;
import javax.swing.SwingUtilities;
import weka.classifiers.AbstractClassifier;
import weka.classifiers.Classifier;
import weka.classifiers.meta.CVParameterSelection;
import weka.classifiers.rules.ZeroR;
import weka.classifiers.trees.J48;
import weka.core.Instances;
import weka.gui.GenericObjectEditor;
import weka.gui.explorer.ClassifierPanel;

/**
 * Runs ZeroR, J48 and CVParameterSelection inside Weka's own ClassifierPanel
 * (the Explorer classify pane) and saves screenshots of the result text.
 */
public class WekaShots {
    static final String ARFF = "/workspace/solution/productivity.arff";
    static final String FIG = "/workspace/solution/figures";

    public static void main(String[] args) throws Exception {
        Files.createDirectories(Path.of(FIG));

        ZeroR zeroR = new ZeroR();
        shoot("zeror", zeroR);

        J48 j48 = new J48();
        j48.setConfidenceFactor(0.1f);
        shoot("j48", j48);

        CVParameterSelection cv = new CVParameterSelection();
        cv.setOptions(new String[] {
            "-X", "10",
            "-S", "1",
            "-P", "C 0.05 0.5 16",
            "-W", "weka.classifiers.trees.J48"
        });
        shoot("cvps", cv);
        System.out.println("done");
    }

    static void shoot(String name, Classifier classifier) throws Exception {
        Classifier copy = AbstractClassifier.makeCopy(classifier);
        PanelRun run = new PanelRun();
        SwingUtilities.invokeAndWait(() -> {
            try {
                run.start(copy);
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        });

        long deadline = System.currentTimeMillis() + 180_000;
        while (System.currentTimeMillis() < deadline) {
            boolean[] running = new boolean[1];
            String[] text = new String[1];
            SwingUtilities.invokeAndWait(() -> {
                try {
                    running[0] = run.thread() != null;
                    text[0] = run.text();
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            });
            if (!running[0] && text[0] != null && text[0].contains("=== Confusion Matrix ===")
                    && text[0].contains("=== Run information ===")) {
                break;
            }
            Thread.sleep(150);
        }

        String full = run.text();
        Files.writeString(Path.of("/workspace/solution/" + name + "-explorer.txt"), full, StandardCharsets.UTF_8);
        if (!full.contains("=== Run information ===")) {
            throw new IllegalStateException(name + " did not produce run information:\n" + full.substring(0, Math.min(500, full.length())));
        }

        if (name.equals("zeror")) {
            grab(run, "=== Run information ===", 15, "q4a-run-information.png", 900, 460, false);
            grab(run, "=== Confusion Matrix ===", 6, "q4a-confusion-matrix.png", 640, 260, false);
        } else if (name.equals("j48")) {
            grab(run, "=== Run information ===", 15, "q4b-run-information.png", 980, 460, false);
            grab(run, "J48 pruned tree", 16, "q4b-tree.png", 920, 520, false);
        } else {
            grab(run, "=== Run information ===", 16, "q4c-run-information.png", 1080, 520, true);
            grab(run, "Cross-validated Parameter selection.", 8, "q4c-selected-c.png", 1100, 320, false);
        }

        SwingUtilities.invokeAndWait(run::dispose);
        System.out.println("saved " + name);
    }

    static String lastMarker(String text, String marker) {
        if (text.lastIndexOf(marker) < 0) {
            throw new IllegalStateException("missing marker " + marker);
        }
        return marker;
    }

    static void grab(PanelRun run, String marker, int lines, String file, int width, int height, boolean wrap) throws Exception {
        SwingUtilities.invokeAndWait(() -> {
            try {
                run.showExcerpt(marker, lines, width, height, wrap);
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        });
        Thread.sleep(400);
        SwingUtilities.invokeAndWait(() -> {
            try {
                run.saveFrame(FIG + "/" + file);
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        });
        System.out.println("  figure " + file);
    }

    static class PanelRun {
        ClassifierPanel panel;
        JFrame frame;
        JTextArea area;
        Field threadField;
        Field areaField;

        void start(Classifier classifier) throws Exception {
            panel = new ClassifierPanel();
            Instances data = new Instances(new FileReader(ARFF));
            data.setClassIndex(data.numAttributes() - 1);
            panel.setInstances(data);

            Field editorField = ClassifierPanel.class.getDeclaredField("m_ClassifierEditor");
            editorField.setAccessible(true);
            GenericObjectEditor editor = (GenericObjectEditor) editorField.get(panel);
            editor.setValue(classifier);

            Field cvButField = ClassifierPanel.class.getDeclaredField("m_CVBut");
            cvButField.setAccessible(true);
            ((JRadioButton) cvButField.get(panel)).setSelected(true);
            Field cvTextField = ClassifierPanel.class.getDeclaredField("m_CVText");
            cvTextField.setAccessible(true);
            ((JTextField) cvTextField.get(panel)).setText("10");

            threadField = ClassifierPanel.class.getDeclaredField("m_RunThread");
            threadField.setAccessible(true);
            areaField = ClassifierPanel.class.getDeclaredField("m_OutText");
            areaField.setAccessible(true);
            area = (JTextArea) areaField.get(panel);

            Method start = ClassifierPanel.class.getDeclaredMethod("startClassifier");
            start.setAccessible(true);
            start.invoke(panel);
        }

        Thread thread() throws Exception {
            return (Thread) threadField.get(panel);
        }

        String text() throws Exception {
            return area.getText();
        }

        void showExcerpt(String marker, int lines, int width, int height, boolean wrap) throws Exception {
            if (frame != null) {
                frame.dispose();
            }
            String text = area.getText();
            int start = text.lastIndexOf(marker);
            if (start < 0) {
                throw new IllegalStateException("marker not found: " + marker);
            }
            int end = start;
            int seen = 0;
            while (end < text.length() && seen < lines) {
                if (text.charAt(end) == '\n') {
                    seen++;
                }
                end++;
            }
            String excerpt = text.substring(start, Math.min(text.length(), end));
            if (!excerpt.endsWith("\n")) {
                excerpt += "\n";
            }

            JTextArea view = new JTextArea(excerpt);
            view.setFont(new Font("Monospaced", Font.PLAIN, 16));
            view.setEditable(false);
            view.setLineWrap(wrap);
            view.setWrapStyleWord(false);
            view.setMargin(new java.awt.Insets(10, 14, 10, 14));
            view.setCaretPosition(0);
            JScrollPane scroll = new JScrollPane(view);
            frame = new JFrame("Weka Explorer");
            frame.add(scroll);
            frame.setSize(width, height);
            frame.setLocation(40, 40);
            frame.setVisible(true);
        }

        void saveFrame(String path) throws Exception {
            frame.setAlwaysOnTop(true);
            frame.toFront();
            Thread.sleep(200);
            Rectangle bounds = frame.getBounds();
            java.awt.Robot robot = new java.awt.Robot();
            BufferedImage image = robot.createScreenCapture(bounds);
            ImageIO.write(image, "png", new File(path));
        }

        void dispose() {
            if (frame != null) {
                frame.dispose();
            }
        }
    }
}
