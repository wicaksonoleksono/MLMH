function phqSettings() {
  return {
    loading: false,

    config: {
      randomize: "false", // Will be loaded from service layer
      instructions: "", // Will be loaded from service layer
    },

    scale: {
      minValue: 0,
      maxValue: 3,
      labels: {}, // Will be loaded from service layer
    },

    categories: [], // Will be loaded from service layer via window.phqData

    settings: {
      id: null,
      instructions: "",
      is_default: false,
    },

    // Modal state
    showModal: false,
    modalTitle: "",
    modalMessage: "",
    modalConfirm: () => {},

    async init() {
      this.updateScale();
      this.loadDataFromTemplate();
    },
    updateScale() {
      this.scale.minValue = 0; // Always start from 0 (0-based)
      const max = parseInt(this.scale.maxValue);
      const newLabels = {};

      for (let i = 0; i <= max; i++) {
        newLabels[i] = this.scale.labels[i] || `Label ${i}`;
      }

      this.scale.labels = newLabels;
    },

    addQuestion(categoryIndex) {
      this.categories[categoryIndex].questions.push("");
    },

    removeQuestion(categoryIndex, questionIndex) {
      this.categories[categoryIndex].questions.splice(questionIndex, 1);
    },

    async loadDefaults() {
      this.showModal = true;
      this.modalTitle = "Muat Data Default";
      this.modalMessage =
        "Apakah Anda yakin ingin memuat data default PHQ-9? Data yang ada akan diganti dengan pertanyaan default yang sudah disediakan.";
      this.modalConfirm = async () => {
        this.loading = true;
        this.showModal = false;
        try {
          // Call API to load default questions into database
          const response = await fetch("/admin/phq/api/defaults", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
          });
          // ss

          const result = await response.json();

          if (result.status === "OLKORECT") {
            // Reload the page to get fresh data with defaults from service layer
            window.location.reload();
          } else {
            alert(
              "Error loading defaults: " + (result.error || "Unknown error")
            );
          }
        } catch (error) {
          alert("Error loading defaults: " + error.message);
        } finally {
          this.loading = false;
        }
      };
    },

    async clearAll() {
      this.showModal = true;
      this.modalTitle = "Hapus Semua Data";
      this.modalMessage =
        "Apakah Anda yakin ingin menghapus semua data PHQ yang ada? (Kecuali pengaturan skala)";
      this.modalConfirm = async () => {
        this.loading = true;
        try {
          // Get all existing data
          const [categories, settings] = await Promise.all([
            apiCall("/admin/phq/categories"),
            apiCall("/admin/phq/settings"),
          ]);

          // Delete categories (this will cascade delete questions)
          if (Array.isArray(categories)) {
            for (const cat of categories) {
              await apiCall(`/admin/phq/categories/${cat.id}`, "DELETE");
            }
          }

          // Delete settings
          if (Array.isArray(settings)) {
            for (const setting of settings) {
              await apiCall(`/admin/phq/settings/${setting.id}`, "DELETE");
            }
          }

          // Reset categories to clean state using service data
          const phqData = window.phqData || {};
          if (phqData.categories && Array.isArray(phqData.categories)) {
            this.categories = phqData.categories.map((cat) => ({
              name_id: cat.name_id, // Constant from service
              name: cat.name, // Constant from service
              description_id: cat.description_id, // Constant from service
              questions: [""], // Reset questions to empty
            }));
          }

          this.settings = {
            id: null,
            instructions: "",
            is_default: false,
          };

          this.showModal = true;
          this.modalTitle = "Berhasil";
          this.modalMessage =
            "Data PHQ berhasil dihapus! (Kecuali pengaturan skala)";
          this.modalConfirm = () => {
            this.showModal = false;
          };
        } catch (error) {
          this.showModal = true;
          this.modalTitle = "Error";
          this.modalMessage = "Error clearing data: " + error.message;
          this.modalConfirm = () => {
            this.showModal = false;
          };
        } finally {
          this.loading = false;
        }
      };
    },

    loadDataFromTemplate() {
      // Load data from Jinja template context (passed via window.phqData)
      const phqData = window.phqData || {};

      try {
        // Load categories from service layer (immutable structure)
        if (phqData.categories && Array.isArray(phqData.categories)) {
          this.categories = phqData.categories.map((cat) => ({
            name_id: cat.name_id, // Constant
            name: cat.name, // Constant
            description_id: cat.description_id, // Constant
            questions:
              phqData.questions_by_category &&
              phqData.questions_by_category[cat.name_id]
                ? phqData.questions_by_category[cat.name_id]
                : [""], // Empty if no questions, NOT description_id
          }));
        }

        // Load scale
        if (phqData.scale) {
          this.scale = {
            id: phqData.scale.id,
            minValue: phqData.scale.min_value,
            maxValue: phqData.scale.max_value,
            labels: phqData.scale.scale_labels,
          };
        }

        // Load settings
        if (phqData.settings) {
          this.config.randomize = phqData.settings.randomize_categories
            ? "true"
            : "false";
          this.config.instructions = phqData.settings.instructions || "";
        }
      } catch (error) {
        console.error("Error loading PHQ data from template:", error);
      }
    },

    // Keep the old async loadData method for fallback
    async loadData() {
      this.loading = true;
      try {
        // Load all PHQ data
        const [categoriesRes, scalesRes, settingsRes] = await Promise.all([
          apiCall("/admin/phq/categories"),
          apiCall("/admin/phq/scales"),
          apiCall("/admin/phq/settings"),
        ]);

        // Load questions for predefined categories
        if (Array.isArray(categoriesRes) && categoriesRes.length > 0) {
          for (const cat of categoriesRes) {
            // Find matching predefined category
            const predefinedCat = this.categories.find(
              (c) => c.name_id === cat.name_id
            );
            if (predefinedCat) {
              // Load questions for this category
              const questionsRes = await apiCall(
                `/admin/phq/questions?category_name_id=${cat.name_id}`
              );
              const questions = Array.isArray(questionsRes)
                ? questionsRes.map((q) => q.question_text_id)
                : [predefinedCat.description_id];

              predefinedCat.questions =
                questions.length > 0
                  ? questions
                  : [predefinedCat.description_id];
            }
          }
        }

        // Load scale (find default or first active scale)
        if (Array.isArray(scalesRes) && scalesRes.length > 0) {
          const scale = scalesRes.find((s) => s.is_default) || scalesRes[0];
          this.scale = {
            id: scale.id,
            minValue: scale.min_value,
            maxValue: scale.max_value,
            labels: scale.scale_labels,
          };
        }

        // Load settings (find default or first active setting)
        if (Array.isArray(settingsRes) && settingsRes.length > 0) {
          const settings =
            settingsRes.find((s) => s.is_default) || settingsRes[0];
          this.config.randomize = settings.randomize_categories
            ? "true"
            : "false";
          this.config.instructions = settings.instructions || "";
        }
      } catch (error) {
      } finally {
        this.loading = false;
      }
    },

    async saveAll() {
      this.loading = true;
      try {
        // Save scale
        const scaleData = {
          scale_name: "PHQ-9 Default",
          min_value: parseInt(this.scale.minValue),
          max_value: parseInt(this.scale.maxValue),
          scale_labels: this.scale.labels,
          is_default: true,
        };

        const scaleResult = await apiCall(
          "/admin/phq/scales",
          "POST",
          scaleData
        );

        if (scaleResult.status === "SNAFU") {
          alert(
            "Error saving scale: " +
              (scaleResult.error || scaleResult.errorMsg || "Unknown error")
          );
          return;
        }

        // Save questions for each category
        for (let i = 0; i < this.categories.length; i++) {
          const category = this.categories[i];

          if (category.questions.length > 0) {
            // Delete existing questions for this category first
            const existingQuestions = await apiCall(
              `/admin/phq/questions?category_name_id=${category.name_id}`
            );
            if (Array.isArray(existingQuestions)) {
              for (const existingQ of existingQuestions) {
                await apiCall(`/admin/phq/questions/${existingQ.id}`, "DELETE");
              }
            }

            // Save new questions
            for (let j = 0; j < category.questions.length; j++) {
              if (category.questions[j].trim()) {
                const questionData = {
                  category_name_id: category.name_id,
                  question_text_en: category.questions[j],
                  question_text_id: category.questions[j],
                  order_index: j,
                };

                const qResult = await apiCall(
                  "/admin/phq/questions",
                  "POST",
                  questionData
                );

                if (qResult.status === "SNAFU") {
                  alert(
                    "Error saving question: " +
                      (qResult.error || qResult.errorMsg || "Unknown error")
                  );
                  return;
                }
              }
            }
          }
        }

        // Save settings
        if (scaleResult.status === "OLKORECT") {
          const settingsData = {
            scale_id: scaleResult.data ? scaleResult.data.id : scaleResult.id,
            randomize_questions: this.config.randomize === "true",
            instructions: this.config.instructions,
            is_default: true,
          };

          const settingsResult = await apiCall(
            "/admin/phq/settings",
            "POST",
            settingsData
          );

          if (settingsResult.status === "SNAFU") {
            alert(
              "Error saving settings: " +
                (settingsResult.error ||
                  settingsResult.errorMsg ||
                  "Unknown error")
            );
            return;
          }
        }

        this.showModal = true;
        this.modalTitle = "Berhasil";
        this.modalMessage = "Semua pengaturan PHQ berhasil disimpan!";
        this.modalConfirm = () => {
          window.location.reload();
        };
      } catch (error) {
        this.showModal = true;
        this.modalTitle = "Error";
        this.modalMessage = "Error saving data: " + error.message;
        this.modalConfirm = () => {};
      } finally {
        this.loading = false;
      }
    },
  };
}
