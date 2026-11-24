// Firebase settings of YOUR course. Open setup.html (the Setup guide) and follow Step 1:
// it builds this file for you. Until then the course cannot connect to a database.
// These values are not secret: the data are protected by the Firestore rules.
const firebaseConfig = {
  apiKey: "PASTE-YOUR-API-KEY",
  authDomain: "your-project.firebaseapp.com",
  projectId: "your-project",
  storageBucket: "your-project.firebasestorage.app",
  messagingSenderId: "000000000000",
  appId: "0:000000000000:web:0000000000000000000000"
};

export { firebaseConfig };

// The first name of the course: shown until you set the title in Teacher's Edition, Course settings.
export const COURSE_TITLE = "My Course";
