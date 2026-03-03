Feature: Form Validation

Background:
  Given the user navigates to "https://example.com/register"

Scenario: User submits valid registration form
  When the user enters "John" into the "first-name" field
  When the user enters "Doe" into the "last-name" field
  When the user enters "john.doe@example.com" into the "email" field
  When the user enters "SecurePass123!" into the "password" field
  When the user enters "SecurePass123!" into the "confirm-password" field
  When the user clicks the "Register" button
  Then the user should see text "Registration successful"
  Then the user should be on the welcome page

Scenario: User submits form with missing email
  When the user enters "John" into the "first-name" field
  When the user enters "Doe" into the "last-name" field
  When the user clicks the "Register" button
  Then the user should see text "Email is required"
