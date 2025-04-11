def translate_email(email_body, target_language):
    # This function will use the OpenAI API to translate the email body.
    import openai

    openai.api_key = 'YOUR_OPENAI_API_KEY'

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": f"Translate the following text to {target_language}: {email_body}"}
        ]
    )

    translation = response['choices'][0]['message']['content']
    return translation

def main():
    # Example email body
    email_body = "Hello, how are you?"
    target_language = "Spanish"

    translated_email = translate_email(email_body, target_language)
    print(translated_email)

if __name__ == "__main__":
    main()
