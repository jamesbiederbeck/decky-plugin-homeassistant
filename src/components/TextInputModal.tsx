import { ConfirmModal, DialogBody, Focusable, TextField } from "@decky/ui";
import { useState } from "react";

interface TextInputModalProps {
  closeModal?: () => void;
  onConfirm: (value: string) => void;
  title: string;
  description?: string;
  initialValue?: string;
  isPassword?: boolean;
  validate?: (value: string) => boolean;
}

const TextInputModal: React.FC<TextInputModalProps> = ({
  closeModal,
  onConfirm,
  title,
  description = "",
  initialValue = "",
  isPassword = false,
  validate,
}) => {
  const [value, setValue] = useState<string>(initialValue);
  const [isValid, setIsValid] = useState<boolean>(
    validate ? validate(initialValue) : true
  );

  const handleChange = (newValue: string) => {
    setValue(newValue);
    if (validate) {
      setIsValid(validate(newValue));
    }
  };

  return (
    <ConfirmModal
      strTitle={title}
      strDescription={description}
      strOKButtonText="Save"
      bOKDisabled={validate ? !isValid : false}
      onCancel={closeModal}
      onOK={() => {
        onConfirm(value);
        closeModal?.();
      }}
    >
      <DialogBody>
        <Focusable>
          <TextField
            value={value}
            bIsPassword={isPassword}
            onChange={(evt) => handleChange(evt.target.value)}
          />
        </Focusable>
      </DialogBody>
    </ConfirmModal>
  );
};

export default TextInputModal;
